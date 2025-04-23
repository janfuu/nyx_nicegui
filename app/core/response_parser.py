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
        DEPRECATED: This regex-based parser is no longer used.
        Please use _llm_parse instead for better tag handling and context awareness.
        
        Parse the response text to extract special tags for mood, thoughts, and appearance changes
        
        Args:
            response_text: The text to parse
            current_appearance: The current appearance description for context (unused in regex version)
        """
        logger = Logger()
        logger.warning("DEPRECATED: Using regex-based parse_response. Please use _llm_parse instead.")
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
        
        # Extract thoughts using regex - handle both formats
        thought_pattern = r'(?:<thought>|\[\[thought\]\])(.*?)(?:</thought>|\[\[/thought\]\])'
        thoughts = re.findall(thought_pattern, response_text, re.DOTALL)
        if thoughts:
            result["thoughts"] = [thought.strip() for thought in thoughts]
            logger.info(f"Found {len(thoughts)} thoughts")
        
        # Extract mood using regex - handle both formats
        mood_pattern = r'(?:<mood>|\[\[mood\]\])(.*?)(?:</mood>|\[\[/mood\]\])'
        moods = re.findall(mood_pattern, response_text, re.DOTALL)
        if moods:
            result["mood"] = moods[-1].strip()  # Use the last mood tag if multiple exist
            logger.info(f"Found mood update: {result['mood']}")
        
        # Extract appearance changes using regex - handle both formats
        appearance_pattern = r'(?:<appearance>|\[\[appearance\]\])(.*?)(?:</appearance>|\[\[/appearance\]\])'
        appearance_changes = re.findall(appearance_pattern, response_text, re.DOTALL)
        if appearance_changes:
            result["appearance"] = [change.strip() for change in appearance_changes]
            logger.info(f"Found {len(appearance_changes)} appearance changes")
        
        # Extract clothing changes using regex - handle both formats
        clothing_pattern = r'(?:<clothing>|\[\[clothing\]\])(.*?)(?:</clothing>|\[\[/clothing\]\])'
        clothing_changes = re.findall(clothing_pattern, response_text, re.DOTALL)
        if clothing_changes:
            result["clothing"] = [change.strip() for change in clothing_changes]
            logger.info(f"Found {len(clothing_changes)} clothing changes")
        
        # Extract location changes using regex - handle both formats
        location_pattern = r'(?:<location>|\[\[location\]\])(.*?)(?:</location>|\[\[/location\]\])'
        locations = re.findall(location_pattern, response_text, re.DOTALL)
        if locations:
            result["location"] = locations[-1].strip()  # Use the last location tag if multiple exist
            logger.info(f"Found location update: {result['location']}")
        
        # Extract images using regex - handle both formats
        image_pattern = r'(?:<image>|\[\[image\]\])(.*?)(?:</image>|\[\[/image\]\])'
        images = re.findall(image_pattern, response_text, re.DOTALL)
        if images:
            result["images"] = [image.strip() for image in images]
            logger.info(f"Found {len(images)} images")
        
        # Clean the main text by removing all tags - handle both formats
        result["main_text"] = re.sub(
            r'(?:<(thought|mood|appearance|clothing|location|image)>|\[\[\1\]\])(.*?)(?:</\1>|\[\[/\1\]\])',
            '',
            response_text,
            flags=re.DOTALL
        ).strip()
        
        logger.info(f"Parsing complete. Found: {len(result['thoughts'])} thoughts, Mood update: {'Yes' if result['mood'] else 'No'}")
        return result

    @staticmethod
    def _clean_json_response(response: str) -> str:
        """Clean up a JSON response to ensure it's properly formatted"""
        # Remove any markdown code block syntax
        response = response.strip()
        if response.startswith("```json"):
            response = response[7:]
        elif response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        response = response.strip()
        
        # First try to parse the response as-is
        try:
            json.loads(response)
            return response  # If it's already valid JSON, return it unchanged
        except json.JSONDecodeError:
            pass  # Continue with cleaning if parsing fails
        
        # Ensure the response is properly terminated
        if not response.endswith("}"):
            # Find the last complete object
            last_brace = response.rfind("}")
            if last_brace != -1:
                response = response[:last_brace + 1]
        
        # Fix missing commas between properties
        # Only fix if there's no comma and the next character is a quote
        response = re.sub(r'("[^"]*"\s*:\s*(?:"[^"]*"|\d+|true|false|null))\s*(?="[^"]*"|})', r'\1,', response)
        
        # Fix missing quotes around property names
        # Only fix if the property name isn't already quoted
        response = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)(\s*:\s*)', r'\1"\2"\3', response)
        
        # Fix missing quotes around string values
        # Only fix if the value isn't already quoted and isn't a number/boolean/null
        response = re.sub(r'("[^"]*"\s*:\s*)([^",}\]]+)([,\]}])', r'\1"\2"\3', response)
        
        # Fix trailing commas
        response = re.sub(r',(\s*[}\]])', r'\1', response)
        
        # Fix multiple commas
        response = re.sub(r',\s*,', ',', response)
        
        # Fix missing commas between array elements
        # Only fix if there's no comma and the next character is a quote or number
        response = re.sub(r'("[^"]*"|\d+|true|false|null)\s*(?="[^"]*"|\d+|true|false|null|[\]])', r'\1,', response)
        
        # Don't try to fix escaped quotes - this was causing problems with valid JSON
        
        return response

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
                "max_tokens": 8192,
                "response_format": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "main_text": {"type": "string"},
                            "thoughts": {"type": "array", "items": {"type": "string"}},
                            "mood": {"type": ["string", "null"]},
                            "appearance": {"type": "array", "items": {"type": "string"}},
                            "images": {"type": "array", "items": {"type": "string"}}
                        },
                        "required": ["main_text", "thoughts", "mood", "appearance", "images"]
                    }
                }
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
                
                # Log the response length and content for debugging
                logger.debug(f"Raw LLM response length: {len(parsed_content)}")
                logger.debug(f"Raw LLM response: {parsed_content}")
                
                # Check for truncation indicators
                if parsed_content.endswith('...') or not parsed_content.strip().endswith('}'):
                    logger.warning("Response appears to be truncated")
                    # Try to complete the JSON if it's truncated
                    if not parsed_content.strip().endswith('}'):
                        parsed_content = parsed_content.strip() + '}'
                
            try:
                # Clean up the response before parsing
                cleaned_content = ResponseParser._clean_json_response(parsed_content)
                
                # Log the cleaned content length
                logger.debug(f"Cleaned response length: {len(cleaned_content)}")
                
                # Try to parse the JSON with error recovery
                result = None
                try:
                    result = json.loads(cleaned_content)
                except json.JSONDecodeError as e:
                    logger.warning(f"Initial JSON parse failed, attempting to fix: {str(e)}")
                    logger.debug(f"Error position: line {e.lineno}, column {e.colno}, char {e.pos}")
                    logger.debug(f"Context around error: {cleaned_content[max(0, e.pos-50):min(len(cleaned_content), e.pos+50)]}")
                    
                    # Try to extract just the JSON object if it's wrapped in text
                    json_match = re.search(r'\{.*\}', cleaned_content, re.DOTALL)
                    if json_match:
                        cleaned_content = json_match.group(0)
                    
                    # Try to fix common JSON issues
                    # 1. Fix missing commas between properties
                    cleaned_content = re.sub(r'("[^"]*"\s*:\s*(?:"[^"]*"|\d+|true|false|null))\s*(?="[^"]*"|})', r'\1,', cleaned_content)
                    # 2. Fix missing quotes around property names
                    cleaned_content = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)(\s*:\s*)', r'\1"\2"\3', cleaned_content)
                    # 3. Fix missing quotes around string values
                    cleaned_content = re.sub(r'("[^"]*"\s*:\s*)([^",}\]]+)([,\]}])', r'\1"\2"\3', cleaned_content)
                    # 4. Fix trailing commas
                    cleaned_content = re.sub(r',(\s*[}\]])', r'\1', cleaned_content)
                    # 5. Fix multiple commas
                    cleaned_content = re.sub(r',\s*,', ',', cleaned_content)
                    # 6. Fix missing commas between array elements
                    cleaned_content = re.sub(r'("[^"]*"|\d+|true|false|null)\s*(?="[^"]*"|\d+|true|false|null|[\]])', r'\1,', cleaned_content)
                    # 7. Fix unescaped quotes in strings
                    cleaned_content = re.sub(r'([^\\])"([^"]*?)([^\\])"', r'\1"\2\\\3"', cleaned_content)
                    
                    try:
                        result = json.loads(cleaned_content)
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse JSON after fixes: {str(e)}")
                        logger.error(f"Content that failed to parse: {cleaned_content}")
                        # Try one last time with a more aggressive cleanup
                        try:
                            # Remove any non-JSON content before the first { and after the last }
                            start = cleaned_content.find('{')
                            end = cleaned_content.rfind('}') + 1
                            if start != -1 and end != 0:
                                cleaned_content = cleaned_content[start:end]
                                result = json.loads(cleaned_content)
                        except json.JSONDecodeError as e:
                            logger.error(f"Final JSON parse attempt failed: {str(e)}")
                            return None
                
                if not isinstance(result, dict):
                    logger.error(f"Invalid response format: {result}")
                    return None
                
                # Ensure required fields exist
                required_fields = ["main_text", "thoughts", "mood", "appearance", "images"]
                for field in required_fields:
                    if field not in result:
                        result[field] = [] if field in ["thoughts", "appearance", "images"] else None
                
                return result
            except Exception as e:
                logger.error(f"Error parsing JSON response: {str(e)}")
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
