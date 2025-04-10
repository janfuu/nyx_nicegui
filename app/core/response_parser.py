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
    def parse_response(response_text):
        """
        Parse the LLM response to extract special tags using LLM parsing
        """
        logger = Logger()
        logger.info("Starting to parse response")
        logger.debug(f"Original response text: {response_text}")
        
        # Get the parsed result using LLM
        result = ResponseParser._llm_parse(response_text)
        
        if not result:
            logger.error("LLM parsing failed")
            # Return a safe fallback structure
            return {
                "thoughts": [],
                "images": [],
                "mood": None
            }
        
        logger.info(f"Parsing complete. Found: {len(result.get('thoughts', []))} thoughts, {len(result.get('images', []))} images, Mood update: {'Yes' if result.get('mood') else 'No'}")
        return result
    
    @staticmethod
    def _llm_parse(response_text):
        """Parse using an LLM for advanced parsing"""
        logger = Logger()
        config = Config()
        
        try:
            # Get parser configuration
            parser_provider = config.get("llm", "parser_provider", "openrouter")
            parser_model = config.get("llm", "parser_model", "anthropic/claude-3-haiku")
            
            logger.info(f"Using parser: {parser_provider}/{parser_model}")
            
            # Get API details based on provider
            if parser_provider == "openrouter":
                api_base = config.get("llm", "openrouter_api_base", "https://openrouter.ai/api/v1")
                api_key = config.get("llm", "openrouter_api_key", "")
                
                # Verify API key
                if not api_key:
                    logger.error("No OpenRouter API key found for parser")
                    return None
                
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "HTTP-Referer": config.get("llm", "http_referer", "http://localhost:8080"),
                    "X-Title": "Nyx AI Assistant - Parser"
                }
            else:
                api_base = config.get("llm", "local_api_base", "http://localhost:5000/v1")
                headers = {"Content-Type": "application/json"}
            
            # Get the parser prompt from the database
            prompt_manager = PromptManager()
            parser_data = prompt_manager.get_prompt("response_parser", PromptType.PARSER.value)
            
            # Get Nyx's description from config
            nyx_description = config.get("character", "description", "")
            
            # Build parsing prompt
            system_prompt = f"""You are a JSON parser that extracts ONLY tagged content from AI responses.
Your task is to extract thoughts, image descriptions, and mood updates from the text.
DO NOT modify or clean the original response text.

IMPORTANT RULES:
1. Only extract content within <thought>, <image>, and <mood> tags
2. When an image involves Nyx (the AI character), you MUST include her full description
3. Do not extract simple actions or gestures as images (like *smiles* or *winks*)
4. Handle incomplete or malformed tags carefully:
   - If a tag is incomplete (e.g., missing closing tag), try to infer the intended content
   - If a tag is malformed, extract the meaningful content if possible
   - If a tag is ambiguous, prefer to not extract it rather than extract incorrectly

Nyx's description is: "{nyx_description}"

Examples of what to extract:
- <thought>I wonder about that</thought> -> extract as thought
- <image>a beautiful sunset over the ocean</image> -> extract as image
- <mood>happy</mood> -> extract as mood
- <image>me standing in a field</image> -> extract as "me standing in a field {nyx_description}"

Examples of what NOT to extract:
- "*smiles gently*"
- "*winks playfully*"
- "*leans in*"
- Simple actions or gestures

YOU MUST RETURN VALID JSON in the following format:
{{
  "thoughts": ["thought1", "thought2"],
  "images": ["image description1", "image description2"],
  "mood": "detected mood or null"
}}

The response MUST be valid JSON. Do not include any explanatory text, just return the JSON object.
Do not include backticks, ```json markers, or "Here is the parsed response:" text.
RETURN ONLY THE JSON OBJECT."""
            
            logger.debug(f"Parser system prompt: {system_prompt}")
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Extract any tagged content from the following AI response:\n\n{response_text}"}
            ]
            
            endpoint = f"{api_base}/chat/completions"
            payload = {
                "model": parser_model,
                "messages": messages,
                "temperature": 0.2,  # Low temperature for more deterministic output
                "max_tokens": 1024,
                "response_format": {"type": "json_object"}  # Request JSON response
            }
            
            logger.debug(f"Parser request to {endpoint}: {json.dumps(payload, default=str, indent=2)}")
            
            response = httpx.post(
                endpoint, 
                json=payload,
                headers=headers,
                timeout=30
            )
            
            logger.debug(f"Parser response status: {response.status_code}")
            response.raise_for_status()
            
            # Parse the response
            response_data = response.json()
            parsed_content = response_data["choices"][0]["message"]["content"]
            
            # Parse the JSON content
            try:
                result = json.loads(parsed_content)
                logger.info("Successfully parsed response with JSON")
                return result
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {str(e)}")
                return None
                
        except Exception as e:
            logger.error(f"Error in LLM parsing: {str(e)}", exc_info=True)
            return None