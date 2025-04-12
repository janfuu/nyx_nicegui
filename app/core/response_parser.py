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
        Parse the LLM response to extract special tags using LLM parsing
        
        Args:
            response_text: The text to parse
            current_appearance: The current appearance description to use for image generation
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
                "images": [],
                "mood": None,
                "self": []
            }
        
        logger.info(f"Parsing complete. Found: {len(result.get('thoughts', []))} thoughts, {len(result.get('images', []))} images, Mood update: {'Yes' if result.get('mood') else 'No'}")
        return result
    
    @staticmethod
    def _llm_parse(response_text, current_appearance=None):
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
            
            # Build parsing prompt
            system_prompt = ResponseParser._get_parser_system_prompt(current_appearance)
            
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

    @staticmethod
    def _get_parser_system_prompt(current_appearance=None) -> str:
        """Get the parser system prompt from the database"""
        prompt_manager = PromptManager()
        parser_data = prompt_manager.get_prompt("response_parser", PromptType.PARSER.value)
        
        if parser_data:
            base_prompt = parser_data["content"]
        else:
            # Fallback to default if not in database
            base_prompt = """You are a structured JSON parser designed to extract tagged content from AI-generated dialogue.
Your job is to detect and transform any <thought>, <image>, <mood>, and <self> tags into structured JSON outputs.

Strictly follow these rules:

1. Extract only content from <thought>, <image>, <mood>, and <self> tags. Ignore all other text.
2. When parsing <image> content involving Nyx (the AI character), you MUST include her **full current description**. This includes:
   - Physical traits (e.g. cybernetic circuits, hair, clothing)
   - Mood or expression
   - Environmental context if available
   - Style and quality keywords
3. Do not extract <image> content for simple non-visual gestures (e.g., *smiles*, *nods*).
4. Handle malformed or incomplete tags as follows:
   - Attempt recovery only if the intended content is obvious
   - If unsure, skip the tag to avoid false positives

For <image> descriptions:
- Rewrite content into an image-generation prompt (Stable Diffusion style)
- Include subject, mood, environment, composition, and visual style
- Use specific stylistic and quality tags like:
   "digital art", "cyberpunk", "cinematic lighting", "unreal engine", "high detail", "sharp focus", "by artgerm", "trending on artstation"
"""

        # Add current appearance if provided
        if current_appearance:
            base_prompt += f"\n\nCURRENT APPEARANCE:\n{current_appearance}\n\nWhen generating image prompts, incorporate this current appearance unless explicitly changed by a <self> tag."

        base_prompt += """\n\n✅ Return **only valid JSON** in the following format:
{
  "main_text": "The cleaned response with all tags removed",
  "thoughts": ["thought1", "thought2"],
  "images": ["score_9, score_8_up, score_7_up, image description1", "score_9, score_8_up, score_7_up, image description2"],
  "mood": "parsed mood or null",
  "self": ["action1", "action2"]
}

No extra commentary, no code blocks. Return only the raw JSON object."""

        return base_prompt
