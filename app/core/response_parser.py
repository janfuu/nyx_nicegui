import json
import httpx
from app.models.prompt_models import PromptManager, PromptType
from app.utils.config import Config
from app.utils.logger import Logger
from enum import Enum

class LLMProvider(Enum):
    LOCAL = "local"
    OPENROUTER = "openrouter"

class ResponseParser:
    @staticmethod
    def parse_response(response_text, current_appearance=None):
        """
        Parse the LLM response to extract special tags and infer mood, thoughts, and appearance
        
        Args:
            response_text: The text to parse
            current_appearance: The current appearance description for context
        """
        logger = Logger()
        logger.info("Starting to parse response")
        logger.debug(f"Original response text: {response_text}")
        logger.debug(f"Current appearance: {current_appearance}")
        
        # Get the parsed result using LLM
        result = ResponseParser._llm_parse(response_text, current_appearance)
        
        if not result:
            logger.error("LLM parsing failed")
            # Return a safe fallback structure
            return {
                "thoughts": [],
                "mood": None,
                "self": [],
                "main_text": response_text
            }
        
        logger.info(f"Parsing complete. Found: {len(result.get('thoughts', []))} thoughts, Mood update: {'Yes' if result.get('mood') else 'No'}")
        return result
    
    @staticmethod
    def _llm_parse(response_text, current_appearance=None):
        """Parse the response using LLM"""
        try:
            config = Config()
            parser_provider = config.get("llm", "parser_provider", "openrouter")
            parser_model = config.get("llm", "parser_model", "mistralai/mistral-large")

            logger = Logger()
            logger.info(f"Using response parser: {parser_provider}/{parser_model}")

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

            # Get system prompt from database
            prompt_manager = PromptManager()
            parser_data = prompt_manager.get_prompt("response_parser", PromptType.RESPONSE_PARSER.value)
            
            if parser_data:
                system_prompt = parser_data["content"]
            else:
                # Fallback to default if not in database
                system_prompt = """You are a JSON parser that extracts structured information from AI responses.
Your task is to extract thoughts, mood changes, and appearance updates from the text.

YOU MUST RETURN VALID JSON in the following format:
{
  "main_text": "The cleaned response with all tags removed",
  "thoughts": ["thought1", "thought2"],
  "mood": "detected mood or null",
  "self": ["action1", "action2"]
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
- Include both explicit <self> tags and implicit descriptions
- Consider the current appearance context

The response MUST be valid JSON. Do not include any explanatory text, just return the JSON object.
Do not include backticks, ```json markers, or "Here is the parsed response:" text.
RETURN ONLY THE JSON OBJECT."""

            # Add current appearance if provided
            if current_appearance:
                system_prompt += f"\n\nCURRENT APPEARANCE:\n{current_appearance}\n\nUse this as context for detecting appearance changes."

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"{response_text}"}
            ]

            endpoint = f"{api_base}/chat/completions"
            payload = {
                "model": parser_model,
                "messages": messages,
                "temperature": 0.2,
                "max_tokens": 1024,
                "response_format": {"type": "json_object"}
            }

            logger.debug(f"Response parser request to {endpoint}: {json.dumps(payload, indent=2)}")

            response = httpx.post(endpoint, json=payload, headers=headers, timeout=30)
            response.raise_for_status()

            response_data = response.json()
            parsed_content = response_data["choices"][0]["message"]["content"]

            try:
                result = json.loads(parsed_content)
                if not isinstance(result, dict):
                    logger.error(f"Invalid response format: {result}")
                    return None
                
                logger.info("Successfully parsed response")
                return result
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {str(e)}")
                return None

        except Exception as e:
            logger.error(f"Error in LLM parsing: {str(e)}")
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
  "self": ["action1", "action2"]
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
- Include both explicit <self> tags and implicit descriptions
- Consider the current appearance context

The response MUST be valid JSON. Do not include any explanatory text, just return the JSON object.
Do not include backticks, ```json markers, or "Here is the parsed response:" text.
RETURN ONLY THE JSON OBJECT."""

        # Add current appearance if provided
        if current_appearance:
            base_prompt += f"\n\nCURRENT APPEARANCE:\n{current_appearance}\n\nUse this as context for detecting appearance changes."

        return base_prompt
