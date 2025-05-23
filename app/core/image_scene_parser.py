"""
Image Scene Parser
=================

This module implements the image scene parsing system that handles:
1. Converting text descriptions into structured image prompts
2. Incorporating character state into image generation
3. Managing image sequence and orientation
4. Validating and formatting image generation requests

The system provides:
- LLM-based scene parsing with state context
- Structured prompt generation
- Multiple provider support (OpenRouter, Local)
- JSON schema validation
- Error handling and logging

Key Features:
- State-aware prompt generation
- Flexible input handling
- Schema validation
- Provider abstraction
- Response parsing and cleanup
"""

import json
import re
import httpx
import asyncio
from app.models.prompt_models import PromptManager, PromptType
from app.utils.config import Config
from app.utils.logger import Logger
from app.core.state_manager import StateManager
from enum import Enum
from typing import List, Dict

class LLMProvider(Enum):
    """
    Supported LLM providers for image scene parsing.
    
    This enum defines the available providers:
    - LOCAL: Local LLM instance
    - OPENROUTER: OpenRouter API service
    """
    LOCAL = "local"
    OPENROUTER = "openrouter"

class ImageSceneParser:
    """
    Image scene parser that converts text descriptions into structured image prompts.
    
    This class handles:
    1. Parsing text descriptions into image generation prompts
    2. Incorporating character state into prompts
    3. Managing image sequences and orientations
    4. Validating and formatting responses
    
    The parser uses an LLM to generate detailed, structured prompts
    that include character state context and scene details.
    """
    
    @staticmethod
    async def parse_images(response_text, current_appearance=None):
        """
        Parse text descriptions into structured image generation prompts.
        
        Args:
            response_text: Text containing image descriptions
            current_appearance: Optional current appearance override
            
        Returns:
            List of structured image prompts or None on error
            
        This method:
        1. Retrieves current character state
        2. Constructs LLM prompts with context
        3. Handles multiple input formats
        4. Validates and formats responses
        5. Manages provider-specific API calls
        """
        logger = Logger()
        logger.info("Starting image parsing from Nyx response")
        logger.debug(f"Original response text: {response_text}")
        logger.debug(f"Current appearance: {current_appearance}")

        try:
            # Get the full character state from state manager
            state_manager = StateManager()
            character_state = state_manager.get_state()
            
            logger.info("Character state for image generation:")
            logger.info(f"  Mood: {character_state.get('mood', 'None')}")
            logger.info(f"  Appearance: {character_state.get('appearance', 'None')[:50]}...")
            logger.info(f"  Clothing: {character_state.get('clothing', 'None')[:50]}...")
            logger.info(f"  Location: {character_state.get('location', 'None')[:50]}...")

            # Get provider configuration
            config = Config()
            parser_provider = config.get("llm", "image_parser_provider", "openrouter")
            parser_model = config.get("llm", "image_parser_model", "mistralai/mistral-small-3.1-24b-instruct")

            logger.info(f"Using image parser: {parser_provider}/{parser_model}")

            # Configure provider-specific settings
            if parser_provider == "openrouter":
                api_base = config.get("llm", "openrouter_api_base", "https://openrouter.ai/api/v1")
                api_key = config.get("llm", "openrouter_api_key", "")
                if not api_key:
                    logger.error("No OpenRouter API key found for image parser")
                    return None

                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "HTTP-Referer": config.get("llm", "http_referer", "http://localhost:8080"),
                    "X-Title": "Nyx AI Assistant - Image Parser"
                }
            else:
                api_base = config.get("llm", "local_api_base", "http://localhost:5000/v1")
                headers = {"Content-Type": "application/json"}

            # Construct system prompt with state context
            prompt_manager = PromptManager()
            parser_data = prompt_manager.get_prompt("image_scene_parser", PromptType.IMAGE_PARSER.value)
            system_prompt = parser_data["content"] if parser_data else ImageSceneParser._default_prompt()

            # Add character state information to system prompt
            system_prompt += f"\n\nCURRENT CHARACTER STATE:\nappearance: {character_state.get('appearance', '')}\nmood: {character_state.get('mood', '')}\nclothing: {character_state.get('clothing', '')}\nlocation: {character_state.get('location', '')}\n"
            
            logger.debug(f"System prompt for image parser:\n{system_prompt}")

            # Handle input data based on its type
            if isinstance(response_text, str):
                try:
                    input_data = json.loads(response_text)
                except json.JSONDecodeError:
                    input_data = {"content": response_text}
            else:
                input_data = response_text

            # Process image descriptions with context
            if isinstance(input_data, dict) and "images" in input_data:
                # Extract sequence information
                sequences = [img.get("sequence", i+1) for i, img in enumerate(input_data["images"])]
                image_text = []
                
                # Use provided context if available, otherwise fallback to state
                mood = input_data.get('mood', character_state.get('mood', 'neutral'))
                appearance = input_data.get('appearance', character_state.get('appearance', ''))
                clothing = input_data.get('clothing', character_state.get('clothing', ''))
                location = input_data.get('location', character_state.get('location', ''))
                
                # Add all context
                image_text.append(f"Current mood: {mood}")
                image_text.append(f"Current appearance: {appearance}")
                image_text.append(f"Current clothing: {clothing}")
                image_text.append(f"Current location: {location}")
                
                # Add all image descriptions
                image_text.extend([f"Image {seq}: {img['content']}" for seq, img in zip(sequences, input_data["images"])])
                image_text = "\n".join(image_text)
            else:
                # For free-text input, add context before the content
                context_prefix = [
                    f"Current mood: {character_state.get('mood', 'neutral')}",
                    f"Current appearance: {character_state.get('appearance', '')}",
                    f"Current clothing: {character_state.get('clothing', '')}",
                    f"Current location: {character_state.get('location', '')}",
                    "Image description:"
                ]
                image_text = "\n".join(context_prefix) + "\n" + (input_data.get("content", "") if isinstance(input_data, dict) else str(input_data))

            # Prepare messages for LLM
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"{image_text}"}
            ]

            logger.debug(f"Full messages for image parser:\n{json.dumps(messages, indent=2)}")

            # Configure request payload
            endpoint = f"{api_base}/chat/completions"
            payload = {
                "model": parser_model,
                "messages": messages,
                "temperature": 0.2,
                "max_tokens": 8192,
                "response_format": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "images": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "prompt": {"type": "string"},
                                        "sequence": {"type": "integer"},
                                        "orientation": {"type": "string", "enum": ["portrait", "landscape"]}
                                    },
                                    "required": ["prompt", "sequence", "orientation"]
                                }
                            }
                        },
                        "required": ["images"]
                    }
                }
            }

            logger.debug(f"Image parser request to {endpoint}: {json.dumps(payload, indent=2)}")

            # Make API request
            async with httpx.AsyncClient() as client:
                response = await client.post(endpoint, json=payload, headers=headers, timeout=60.0)
                
                if response.status_code != 200:
                    error_data = response.json()
                    error_msg = error_data.get("error", {}).get("message", "Unknown error")
                    error_code = error_data.get("error", {}).get("code", response.status_code)
                    logger.error(f"OpenRouter error: {error_msg} (code: {error_code})")
                    logger.error(f"Error details: {error_data}")
                    return None
                
                response_data = response.json()
                
                # Handle different response formats
                if "choices" in response_data:
                    parsed_content = response_data["choices"][0]["message"]["content"]
                elif "message" in response_data:
                    parsed_content = response_data["message"]["content"]
                else:
                    parsed_content = response_data.get("content", str(response_data))
            
            logger.debug(f"Raw LLM response: {parsed_content}")

            if not parsed_content:
                logger.error("Empty response from LLM")
                return None

            # Parse and validate response
            parsed_content = ImageSceneParser._parse_response(parsed_content)

            try:
                result = json.loads(parsed_content)
                
                # Validate response structure
                if not isinstance(result, dict):
                    logger.error(f"Response is not a dictionary: {result}")
                    return None
                    
                if "images" not in result:
                    logger.error(f"Response missing 'images' key: {result}")
                    return None
                
                images = result["images"]
                if not isinstance(images, list):
                    logger.error(f"Images is not a list: {images}")
                    return None
                
                # Validate each image entry
                for i, image in enumerate(images):
                    if not isinstance(image, dict):
                        logger.error(f"Image {i} is not a dictionary: {image}")
                        return None
                    if "prompt" not in image:
                        logger.error(f"Image {i} missing 'prompt' key: {image}")
                        return None
                
                logger.info("Successfully parsed image scenes")
                return images
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {str(e)}")
                logger.error(f"Raw content that failed to parse: {parsed_content}")
                return None

        except Exception as e:
            logger.error(f"Error in image scene parsing: {str(e)}", exc_info=True)
            return None

    @staticmethod
    def _default_prompt() -> str:
        """
        Get the default system prompt for image scene parsing.
        
        Returns:
            str: The default prompt template
            
        This prompt instructs the LLM to:
        1. Convert text descriptions to image prompts
        2. Consider character state
        3. Format output as JSON
        4. Include sequence and orientation
        """
        return """You are a specialized visual scene parser for an AI character. Your task is to convert free text descriptions or image tags into specific, detailed image prompts.

INSTRUCTIONS:
1. Interpret the input which may contain one or more image descriptions.
2. For each image description, create a detailed, structured prompt.
3. Pay special attention to the character's current appearance, mood, clothing, and location.
4. Respond in JSON format with a list of scene descriptions.

Consider these elements when creating the image prompts:
- Maintain the character's described appearance
- Respect the current location/setting
- Capture the mood and emotion
- Include visual details like lighting, composition, and style
- Aim for photorealistic, high-quality images

FORMAT YOUR RESPONSE AS THIS JSON:
{
  "images": [
    {
      "prompt": "Detailed image prompt text",
      "sequence": 1,
      "orientation": "portrait"
    },
    {
      "prompt": "Another detailed image prompt",
      "sequence": 2,
      "orientation": "portrait"
    }
  ]
}

The "orientation" field should be either "portrait" (default, for vertical images) or "landscape" (for horizontal images) based on what's most appropriate for the scene.

DO NOT include HTML tags, markdown formatting, or explanations. Return ONLY the JSON object."""

    @staticmethod
    def _parse_response(response: str) -> str:
        """
        Clean and parse the LLM response to extract valid JSON.
        
        Args:
            response: Raw response string from LLM
            
        Returns:
            str: Cleaned JSON string
            
        This method:
        1. Removes markdown code blocks
        2. Ensures proper JSON termination
        3. Handles malformed responses
        4. Returns clean JSON string
        """
        # Remove any markdown code block syntax
        response = response.strip()
        if response.startswith("```json"):
            response = response[7:]
        elif response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        response = response.strip()
        
        # Ensure the response is properly terminated
        if not response.endswith("}"):
            # Find the last complete object
            last_brace = response.rfind("}")
            if last_brace != -1:
                response = response[:last_brace + 1]
        
        return response