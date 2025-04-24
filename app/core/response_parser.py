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
        
        Parse a response text and extract structured information.
        Returns a dictionary with the following keys:
        - main_text: The cleaned response text
        - thoughts: List of thoughts
        - mood: Current mood
        - appearance: List of appearance changes
        - clothing: List of clothing changes
        - location: Current location
        """
        logger = Logger()
        logger.warning("DEPRECATED: Using regex-based parse_response. Please use _llm_parse instead.")
        logger.info("Starting to parse response")
        logger.debug(f"Original response text: {response_text}")
        
        result = {
            "main_text": "",
            "thoughts": [],
            "mood": None,
            "appearance": [],
            "clothing": [],
            "location": None
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
        
        # Clean the main text by removing all tags - handle both formats
        result["main_text"] = re.sub(
            r'(?:<(thought|mood|appearance|clothing|location)>|\[\[\1\]\])(.*?)(?:</\1>|\[\[/\1\]\])',
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
        
        return response

    @staticmethod
    async def _llm_parse(text: str, current_appearance: str = None) -> dict:
        """Parse LLM response using the response schema"""
        logger = Logger()
        config = Config()
        
        try:
            # Get parser configuration
            parser_provider = config.get("llm", "response_parser_provider", "openrouter")
            parser_model = config.get("llm", "response_parser_model", "mistralai/mistral-small-3.1-24b-instruct")
            
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
            
            # Get the system prompt
            system_prompt = ResponseParser._get_parser_system_prompt(current_appearance)
            
            # Add character state information to system prompt
            system_prompt += f"\n\nCURRENT CHARACTER STATE:\nappearance: {current_appearance}\n"
            
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
                            "moment": {"type": ["string", "null"]},
                            "secret": {"type": "array", "items": {"type": "string"}}
                        },
                        "required": ["main_text", "thoughts", "mood", "appearance", "moment", "secret"]
                    }
                }
            }
            
            logger.debug(f"Response parser request to {endpoint}: {json.dumps(payload, indent=2)}")
            
            # Use async client for HTTP requests
            async with httpx.AsyncClient() as client:
                # Use a longer timeout for LLM requests (60 seconds)
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
                    # OpenAI format
                    parsed_content = response_data["choices"][0]["message"]["content"]
                elif "message" in response_data:
                    # Direct message format
                    parsed_content = response_data["message"]["content"]
                else:
                    # Try to get content directly
                    parsed_content = response_data.get("content", str(response_data))
            
            # Log the raw LLM response
            logger.debug(f"Raw LLM response: {parsed_content}")
            
            # Check if we got a valid response
            if not parsed_content:
                logger.error("Empty response from LLM")
                return None
            
            # Parse the response to ensure it's properly terminated
            parsed_content = ResponseParser._clean_json_response(parsed_content)
            
            try:
                # Try to parse the response
                result = json.loads(parsed_content)
                
                # Validate the response structure
                if not isinstance(result, dict):
                    logger.error(f"Response is not a dictionary: {result}")
                    return None
                
                # Ensure required fields exist
                required_fields = ["main_text", "thoughts", "mood", "appearance"]
                for field in required_fields:
                    if field not in result:
                        result[field] = [] if field in ["thoughts", "appearance"] else None
                
                return result
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {str(e)}")
                logger.error(f"Raw content that failed to parse: {parsed_content}")
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
