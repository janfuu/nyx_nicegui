import json
import re
import httpx
import asyncio
from app.models.prompt_models import PromptManager, PromptType
from app.utils.config import Config
from app.utils.logger import Logger
from enum import Enum

class LLMProvider(Enum):
    LOCAL = "local"
    OPENROUTER = "openrouter"

class ImageSceneParser:
    @staticmethod
    async def parse_images(response_text, current_appearance=None):
        logger = Logger()
        logger.info("Starting image parsing from Nyx response")
        logger.debug(f"Original response text: {response_text}")
        logger.debug(f"Current appearance: {current_appearance}")

        try:
            # Get the full character state
            from app.core.memory_system import MemorySystem
            memory_system = MemorySystem()
            character_state = memory_system.get_character_state()
            
            logger.info("Character state for image generation:")
            logger.info(f"  Mood: {character_state.get('mood', 'None')}")
            logger.info(f"  Appearance: {character_state.get('appearance', 'None')[:50]}...")
            logger.info(f"  Clothing: {character_state.get('clothing', 'None')[:50]}...")
            logger.info(f"  Location: {character_state.get('location', 'None')[:50]}...")

            config = Config()
            parser_provider = config.get("llm", "parser_provider", "openrouter")
            parser_model = config.get("llm", "parser_model", "mistralai/mistral-large")

            logger.info(f"Using image parser: {parser_provider}/{parser_model}")

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

            # Construct system prompt
            prompt_manager = PromptManager()
            parser_data = prompt_manager.get_prompt("image_scene_parser", PromptType.IMAGE_PARSER.value)
            system_prompt = parser_data["content"] if parser_data else ImageSceneParser._default_prompt()

            # Add character state information to system prompt
            system_prompt += f"\n\nCURRENT CHARACTER STATE:\nappearance: {character_state.get('appearance', '')}\nmood: {character_state.get('mood', '')}\nclothing: {character_state.get('clothing', '')}\nlocation: {character_state.get('location', '')}\n"
            
            logger.debug(f"System prompt for image parser:\n{system_prompt}")

            # Parse the input JSON if it's a JSON string
            try:
                input_data = json.loads(response_text)
                if isinstance(input_data, dict) and "images" in input_data:
                    # Extract sequence information
                    sequences = [img.get("sequence", i+1) for i, img in enumerate(input_data["images"])]
                    # Join all image contents with context
                    image_text = []
                    
                    # Use provided context if available, otherwise fallback to character state
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
                    image_text = "\n".join(context_prefix) + "\n" + response_text
            except json.JSONDecodeError:
                # For free-text input, add context before the content
                context_prefix = [
                    f"Current mood: {character_state.get('mood', 'neutral')}",
                    f"Current appearance: {character_state.get('appearance', '')}",
                    f"Current clothing: {character_state.get('clothing', '')}",
                    f"Current location: {character_state.get('location', '')}",
                    "Image description:"
                ]
                image_text = "\n".join(context_prefix) + "\n" + response_text

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"{image_text}"}
            ]

            logger.debug(f"Full messages for image parser:\n{json.dumps(messages, indent=2)}")

            endpoint = f"{api_base}/chat/completions"
            payload = {
                "model": parser_model,
                "messages": messages,
                "temperature": 0.2,
                "max_tokens": 1024,
                "response_format": {"type": "json_object"}
            }

            logger.debug(f"Image parser request to {endpoint}: {json.dumps(payload, indent=2)}")

            # Use async client for HTTP requests
            async with httpx.AsyncClient() as client:
                # Use a longer timeout for LLM requests (60 seconds)
                response = await client.post(endpoint, json=payload, headers=headers, timeout=60.0)
                response.raise_for_status()

                response_data = response.json()
                parsed_content = response_data["choices"][0]["message"]["content"]
            
            # Log the raw LLM response
            print("=== RAW LLM RESPONSE ===")
            print(parsed_content)
            print("=== END RAW LLM RESPONSE ===")

            try:
                result = json.loads(parsed_content)
                if not isinstance(result, dict) or "images" not in result:
                    logger.error(f"Invalid response format: {result}")
                    return None
                
                images = result["images"]
                if not isinstance(images, list):
                    logger.error(f"Images is not a list: {images}")
                    return None
                
                # Return the images exactly as received from the LLM
                logger.info("Successfully parsed image scenes")
                return images
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {str(e)}")
                return None

        except Exception as e:
            logger.error(f"Error in image scene parsing: {str(e)}", exc_info=True)
            return None

    @staticmethod
    def _default_prompt() -> str:
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