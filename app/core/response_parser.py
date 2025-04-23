import json
import re
import os
from app.models.prompt_models import PromptManager, PromptType
from app.utils.config import Config
from app.utils.logger import Logger
from enum import Enum
import httpx
import jsonschema
from pathlib import Path

class LLMProvider(Enum):
    LOCAL = "local"
    OPENROUTER = "openrouter"

class ResponseParser:
    @staticmethod
    def _close_unclosed_tags(text: str) -> str:
        """
        Close any unclosed tags in the text. Tags are closed when encountering:
        - A newline
        - A new opening tag
        - A period
        - End of text
        
        Args:
            text: The text to process
            
        Returns:
            The text with all unclosed tags properly closed
        """
        # First, find all unique tags in the text
        # This pattern matches any opening tag that starts with a letter and contains letters, numbers, or hyphens
        tag_pattern = r'<([a-z][a-z0-9-]*)>'
        tags = set(re.findall(tag_pattern, text))
        
        logger = Logger()
        logger.debug(f"Found tags to process: {tags}")
        
        # Process each tag type
        for tag in tags:
            # First check if there are any unclosed tags by counting opening and closing tags
            opening_tags = len(re.findall(f'<{tag}>', text))
            closing_tags = len(re.findall(f'</{tag}>', text))
            
            if opening_tags <= closing_tags:
                # All tags are properly closed, skip this tag type
                continue
                
            # Pattern to find unclosed tags - matches opening tag not followed by closing tag
            # until a newline, new opening tag, period, or end of text
            pattern = f'<{tag}>(.*?)(?=<[a-z]+>|[.]|[\n]|$)'
            
            # Find all matches (there could be multiple unclosed tags)
            index_shift = 0
            for match in re.finditer(pattern, text, flags=re.DOTALL):
                start_idx = match.start() + index_shift
                end_idx = match.end() + index_shift
                content = match.group(1)
                
                # Check if this tag is actually closed later in the text
                remaining_text = text[end_idx:]
                if f'</{tag}>' in remaining_text:
                    # Tag is closed later, skip this one
                    continue
                
                # Close the tag properly by inserting the closing tag
                closing_tag = f'</{tag}>'
                text = text[:end_idx] + closing_tag + text[end_idx:]
                
                # Update the index shift for subsequent matches
                index_shift += len(closing_tag)
                
                logger.debug(f"Closed unclosed <{tag}> tag at position {start_idx}")
        
        return text

    @staticmethod
    def parse_response(response_text, current_appearance=None):
        """
        Parse the response text to extract special tags for mood, thoughts, and appearance changes
        
        Args:
            response_text: The text to parse
            current_appearance: The current appearance description for context (unused in regex version)
        """
        logger = Logger()
        logger.info("Starting to parse response")
        logger.debug(f"Original response text: {response_text}")
        
        # First, close any unclosed tags
        response_text = ResponseParser._close_unclosed_tags(response_text)
        logger.debug(f"Response text after closing tags: {response_text}")
        
        # Initialize result structure
        result = {
            "thoughts": [],
            "mood": None,
            "appearance": [],
            "location": None,
            "clothing": [],
            "main_text": response_text,
            "images": []
        }
        
        # Extract thoughts using regex
        thought_pattern = r'<thought>(.*?)</thought>'
        thoughts = re.findall(thought_pattern, response_text, re.DOTALL)
        if thoughts:
            result["thoughts"] = [thought.strip() for thought in thoughts]
            logger.info(f"Found {len(thoughts)} thoughts")
        
        # Extract mood using regex
        mood_pattern = r'<mood>(.*?)</mood>'
        moods = re.findall(mood_pattern, response_text, re.DOTALL)
        if moods:
            result["mood"] = moods[-1].strip()  # Use the last mood tag if multiple exist
            logger.info(f"Found mood update: {result['mood']}")
        
        # Extract appearance changes using regex
        appearance_pattern = r'<appearance>(.*?)</appearance>'
        appearance_changes = re.findall(appearance_pattern, response_text, re.DOTALL)
        if appearance_changes:
            result["appearance"] = [change.strip() for change in appearance_changes]
            logger.info(f"Found {len(appearance_changes)} appearance changes")
        
        # Extract clothing changes using regex
        clothing_pattern = r'<clothing>(.*?)</clothing>'
        clothing_changes = re.findall(clothing_pattern, response_text, re.DOTALL)
        if clothing_changes:
            result["clothing"] = [change.strip() for change in clothing_changes]
            logger.info(f"Found {len(clothing_changes)} clothing changes")
        
        # Extract location changes using regex
        location_pattern = r'<location>(.*?)</location>'
        locations = re.findall(location_pattern, response_text, re.DOTALL)
        if locations:
            result["location"] = locations[-1].strip()  # Use the last location tag if multiple exist
            logger.info(f"Found location update: {result['location']}")
        
        # Extract images using regex
        image_pattern = r'<image>(.*?)</image>'
        images = re.findall(image_pattern, response_text, re.DOTALL)
        if images:
            result["images"] = [image.strip() for image in images]
            logger.info(f"Found {len(images)} images")
        
        # Clean the main text by removing all tags
        result["main_text"] = re.sub(r'<(thought|mood|appearance|clothing|location|image)>(.*?)</\1>', '', response_text, flags=re.DOTALL).strip()
        
        logger.info(f"Parsing complete. Found: {len(result['thoughts'])} thoughts, Mood update: {'Yes' if result['mood'] else 'No'}")
        return result

    @staticmethod
    async def _llm_parse(text: str, current_appearance: str = None) -> dict:
        """Parse LLM response using the response schema"""
        logger = Logger()
        try:
            # Get the full character state
            from app.core.memory_system import MemorySystem
            memory_system = MemorySystem()
            character_state = memory_system.get_character_state()
            
            # Get LLM configuration
            config = Config()
            parser_provider = config.get("llm", "parser_provider", "openrouter")
            parser_model = config.get("llm", "parser_model", "mistralai/mistral-large")
            
            if parser_provider == "openrouter":
                api_base = config.get("llm", "openrouter_api_base", "https://openrouter.ai/api/v1")
                api_key = config.get("llm", "openrouter_api_key", "")
                if not api_key:
                    logger.error("No OpenRouter API key found for response parser")
                    return None
                    
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "HTTP-Referer": config.get("llm", "http_referer", "http://localhost:8080"),
                    "X-Title": "Nyx AI Assistant - Response Parser"
                }
            else:
                api_base = config.get("llm", "local_api_base", "http://localhost:5000/v1")
                headers = {"Content-Type": "application/json"}
            
            # Construct system prompt
            prompt_manager = PromptManager()
            parser_data = prompt_manager.get_prompt("response_parser", PromptType.RESPONSE_PARSER.value)
            system_prompt = parser_data["content"] if parser_data else ResponseParser._default_prompt()
            
            # Add character state information to system prompt
            system_prompt += f"\n\nCURRENT CHARACTER STATE:\nappearance: {character_state.get('appearance', '')}\nmood: {character_state.get('mood', '')}\nclothing: {character_state.get('clothing', '')}\nlocation: {character_state.get('location', '')}\n"
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ]
            
            endpoint = f"{api_base}/chat/completions"
            payload = {
                "model": parser_model,
                "messages": messages,
                "temperature": 0.2,
                "max_tokens": 1024
            }
            
            logger.debug(f"Response parser request to {endpoint}: {json.dumps(payload, indent=2)}")
            
            async with httpx.AsyncClient() as client:
                response = await client.post(endpoint, json=payload, headers=headers, timeout=60.0)
                response.raise_for_status()
                
                response_data = response.json()
                
                # Check for OpenRouter error response
                if "error" in response_data:
                    error_msg = response_data["error"].get("message", "Unknown error")
                    error_code = response_data["error"].get("code", "Unknown code")
                    logger.error(f"OpenRouter error: {error_msg} (code: {error_code})")
                    return None
                
                # Handle different response formats
                if "choices" in response_data:
                    # OpenAI format
                    parsed_content = response_data["choices"][0]["message"]["content"]
                elif "message" in response_data:
                    # Direct message format
                    parsed_content = response_data["message"]["content"]
                else:
                    # Try to get content directly
                    parsed_content = response_data.get("content", str(response_data))
                
                logger.debug(f"Raw LLM response: {parsed_content}")
            
            try:
                result = json.loads(parsed_content)
                if not isinstance(result, dict):
                    logger.error(f"Invalid response format: {result}")
                    return None
                
                return result
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {str(e)}")
                return None
                
        except Exception as e:
            logger.error(f"Error in LLM parsing: {str(e)}", exc_info=True)
            return None

    @staticmethod
    def _get_parser_system_prompt(current_appearance=None) -> str:
        """Get the parser system prompt from the database"""
        prompt_manager = PromptManager()
        parser_data = prompt_manager.get_prompt("response_parser", PromptType.RESPONSE_PARSER.value)
        
        if parser_data:
            base_prompt = parser_data["content"]
        else:
            # Fallback to default if not in database
            base_prompt = """You are a JSON parser that extracts structured information from AI responses.
Your task is to extract thoughts, mood changes, and appearance updates from the text.

YOU MUST RETURN VALID JSON in the following format:
{
  "main_text": "The cleaned response with all tags removed",
  "thoughts": ["thought1", "thought2"],
  "mood": "detected mood or null",
  "appearance": ["action1", "action2"]
}

IMPORTANT RULES:

1. Extract thoughts that are explicitly marked with <thought> tags
2. Infer mood changes from the text, even if not explicitly tagged
3. Detect appearance changes or descriptions in the text
4. Return the main text with all special tags removed

For mood detection:
- Look for emotional language and tone
- Consider context and previous mood
- Return null if no clear mood change is detected

For appearance detection:
- Look for descriptions of physical changes or actions
- Include both explicit <appearance> tags and implicit descriptions
- Consider the current appearance context

The response MUST be valid JSON. Do not include any explanatory text, just return the JSON object.
Do not include backticks, ```json markers, or "Here is the parsed response:" text.
RETURN ONLY THE JSON OBJECT."""

        # Add current appearance if provided
        if current_appearance:
            base_prompt += f"\n\nCURRENT APPEARANCE:\n{current_appearance}\n\nUse this as context for detecting appearance changes."

        return base_prompt
