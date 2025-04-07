import re
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
        Parse the LLM response to extract special tags
        First attempts regex parsing, then falls back to LLM parsing if needed
        """
        # Get the parsing instructions from the database
        prompt_manager = PromptManager()
        parser_data = prompt_manager.get_prompt("response_parser", PromptType.PARSER.value)
        
        # Try regex parsing first
        result = ResponseParser._regex_parse(response_text, parser_data)
        
        # If we didn't find any tags, try LLM parsing
        if not (result.get("thoughts") or result.get("images") or result.get("mood")):
            llm_result = ResponseParser._llm_parse(response_text)
            if llm_result:
                return llm_result
        
        return result
    
    @staticmethod
    def _regex_parse(response_text, parser_data=None):
        """Parse using regular expressions"""
        # Extract thought tags (supporting both <thought> and *thought* formats)
        thoughts = []
        thought_patterns = [
            re.compile(r'<thought>(.*?)<\/thought>', re.DOTALL),
            re.compile(r'\*thought\*(.*?)\*thought\*', re.DOTALL),
            re.compile(r'\*\*thought\*\*(.*?)\*\*thought\*\*', re.DOTALL)
        ]
        
        main_text = response_text
        for pattern in thought_patterns:
            for match in pattern.finditer(main_text):
                thoughts.append(match.group(1).strip())
            main_text = pattern.sub('', main_text)
        
        # Extract image tags (supporting both <image> and *image* formats)
        images = []
        image_patterns = [
            re.compile(r'<image>(.*?)<\/image>', re.DOTALL),
            re.compile(r'\*image\*(.*?)\*image\*', re.DOTALL),
            re.compile(r'\*\*image\*\*(.*?)\*\*image\*\*', re.DOTALL)
        ]
        
        for pattern in image_patterns:
            for match in pattern.finditer(main_text):
                images.append(match.group(1).strip())
            main_text = pattern.sub('', main_text)
        
        # Extract mood tag (supporting both <mood> and *mood* formats)
        mood = None
        mood_patterns = [
            re.compile(r'<mood>(.*?)<\/mood>', re.DOTALL),
            re.compile(r'\*mood\*(.*?)\*mood\*', re.DOTALL),
            re.compile(r'\*\*mood\*\*(.*?)\*\*mood\*\*', re.DOTALL)
        ]
        
        for pattern in mood_patterns:
            mood_match = pattern.search(main_text)
            if mood_match:
                mood = mood_match.group(1).strip()
                main_text = pattern.sub('', main_text)
                break
        
        # Clean up extra whitespace and line breaks
        main_text = re.sub(r'\n{3,}', '\n\n', main_text.strip())
        
        return {
            "main_text": main_text,
            "thoughts": thoughts,
            "images": images,
            "mood": mood
        }
    
    @staticmethod
    def _llm_parse(response_text):
        """Parse using an LLM for more advanced parsing"""
        logger = Logger()
        config = Config()
        
        try:
            # Get a smaller, faster model for parsing
            parser_provider = config.get("llm", "parser_provider", "openrouter")
            parser_model = config.get("llm", "parser_model", "anthropic/claude-3-haiku")
            
            # Get API details based on provider
            if parser_provider == "openrouter":
                api_base = config.get("llm", "openrouter_api_base", "https://openrouter.ai/api/v1")
                api_key = config.get("llm", "openrouter_api_key", "")
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "HTTP-Referer": config.get("llm", "http_referer", "http://localhost:8080"),
                    "X-Title": "Nyx AI Assistant"
                }
            else:
                api_base = config.get("llm", "local_api_base", "http://localhost:5000/v1")
                headers = {"Content-Type": "application/json"}
            
            # Build parsing prompt
            system_prompt = """You are a precise parser that extracts structured information from AI responses.
Extract any thoughts, image descriptions, and mood updates from the text, following these guidelines:

1. Thoughts: Look for text that represents internal thoughts of the AI, often marked with <thought>...</thought>, *thought*...*thought*, or similar markers.
2. Images: Look for descriptions meant for image generation, often marked with <image>...</image>, *image*...*image*, or similar markers.
3. Mood: Look for mood/emotional state updates, often marked with <mood>...</mood>, *mood*...*mood*, or similar markers.

Return a JSON object with the following structure:
{
  "main_text": "The cleaned response with all tags removed",
  "thoughts": ["thought1", "thought2", ...],
  "images": ["image description1", "image description2", ...],
  "mood": "detected mood or null if not found"
}

Be thorough and don't miss any information. Include all text not belonging to special tags in main_text."""
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Parse the following AI response and extract any thoughts, images, and mood updates:\n\n{response_text}"}
            ]
            
            endpoint = f"{api_base}/chat/completions"
            payload = {
                "model": parser_model,
                "messages": messages,
                "temperature": 0.2,  # Low temperature for more deterministic output
                "max_tokens": 1024,
                "response_format": {"type": "json_object"}  # Request JSON response
            }
            
            logger.debug(f"Sending request to parser LLM: {parser_model}")
            response = httpx.post(
                endpoint, 
                json=payload,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            
            response_data = response.json()
            parsed_content = response_data["choices"][0]["message"]["content"]
            
            try:
                result = json.loads(parsed_content)
                logger.debug("Successfully parsed response with LLM")
                return result
            except json.JSONDecodeError:
                logger.warning(f"LLM returned invalid JSON: {parsed_content[:100]}...")
                return None
                
        except Exception as e:
            logger.error(f"Error in LLM parsing: {str(e)}")
            return None