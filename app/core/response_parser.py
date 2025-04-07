import json
import re
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
        
        # Attempt regex parsing first for emergency fallback
        regex_result = ResponseParser._regex_parse(response_text)
        
        # Get the parsed result using LLM
        result = ResponseParser._llm_parse(response_text)
        
        # If LLM parsing fails, use regex result
        if not result:
            logger.warning("LLM parsing failed, using regex fallback")
            return regex_result
        
        logger.info(f"Parsing complete. Found: {len(result.get('thoughts', []))} thoughts, {len(result.get('images', []))} images, Mood update: {'Yes' if result.get('mood') else 'No'}")
        return result
    
    @staticmethod
    def _regex_parse(response_text):
        """Basic regex parsing as fallback"""
        logger = Logger()
        
        # Very simple regex parsing for emergencies
        import re
        
        # Default structure
        result = {
            "main_text": response_text,
            "thoughts": [],
            "images": [],
            "mood": None
        }
        
        # Try to find the most common formats
        # Thoughts - formats like *thought* text *thought* or <thought>text</thought>
        thought_patterns = [
            r'\*thought\*(.*?)\*thought\*',
            r'\*thoughts?\*(.*?)\*thoughts?\*', 
            r'<thought>(.*?)</thought>',
            r'\*thought\*\s+(.*?)(?:\*external\*|\*thought\*|$)'
        ]
        
        cleaned_text = response_text
        for pattern in thought_patterns:
            matches = re.findall(pattern, cleaned_text, re.DOTALL)
            if matches:
                result["thoughts"].extend([m.strip() for m in matches])
                cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.DOTALL)
        
        # Images - formats like *image* text *image* or <image>text</image>
        image_patterns = [
            r'\*image\*(.*?)\*image\*',
            r'<image>(.*?)</image>'
        ]
        
        for pattern in image_patterns:
            matches = re.findall(pattern, cleaned_text, re.DOTALL)
            if matches:
                result["images"].extend([m.strip() for m in matches])
                cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.DOTALL)
        
        # Extract landscape descriptions as images too
        # Look for descriptive text about scenery, landscapes, etc.
        scenery_pattern = r'(?:picture this|imagine|visualize|close your eyes and (?:picture|see)):\s*(.*?)(?:\.|$)'
        scenery_matches = re.findall(scenery_pattern, cleaned_text, re.DOTALL | re.IGNORECASE)
        if scenery_matches:
            for match in scenery_matches:
                if len(match.strip()) > 30:  # Only use substantial descriptions
                    result["images"].append(match.strip())
        
        # Mood - formats like *mood* text *mood* or <mood>text</mood>
        mood_patterns = [
            r'\*mood\*(.*?)\*mood\*',
            r'<mood>(.*?)</mood>',
            r"I'm feeling (.*?)(?:\.|$)",
            r"my mood is (.*?)(?:\.|$)"
        ]
        
        for pattern in mood_patterns:
            match = re.search(pattern, cleaned_text, re.DOTALL | re.IGNORECASE)
            if match:
                result["mood"] = match.group(1).strip()
                cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.DOTALL)
                break
        
        # Clean up various markers
        clean_patterns = [
            r'\*external\*',
            r'\*nods\*',
            r'\*smiles\*',
            r'\*winks\*',
            r'\*pauses\*',
            r'\*chuckles\*'
        ]
        
        for pattern in clean_patterns:
            cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.DOTALL)
        
        # Clean up extra whitespace and line breaks
        result["main_text"] = re.sub(r'\s+', ' ', cleaned_text).strip()
        
        logger.debug(f"Regex parsing result: {json.dumps(result, indent=2)}")
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
            
            # Build parsing prompt
            system_prompt = """You are a JSON parser that extracts structured information from AI responses.
Your only task is to extract thoughts, image descriptions, and mood updates from the text.

YOU MUST RETURN VALID JSON in the following format:
{
  "main_text": "The cleaned response with all tags removed",
  "thoughts": ["thought1", "thought2"],
  "images": ["image description1", "image description2"],
  "mood": "detected mood or null"
}

Look for patterns like:
- Thoughts: <thought>...</thought>, *thought*..., or similar patterns
- Images: <image>...</image>, landscape descriptions, or similar patterns
- Mood: <mood>...</mood>, "I'm feeling...", or similar patterns

The response MUST be valid JSON. Do not include any explanatory text, just return the JSON object.
Do not include backticks, ```json markers, or "Here is the parsed response:" text.
RETURN ONLY THE JSON OBJECT."""
            
            logger.debug(f"Parser system prompt: {system_prompt}")
            
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
            
            logger.debug(f"Parser request to {endpoint}: {json.dumps(payload, default=str, indent=2)}")
            
            response = httpx.post(
                endpoint, 
                json=payload,
                headers=headers,
                timeout=30
            )
            
            logger.debug(f"Parser response status: {response.status_code}")
            response.raise_for_status()
            
            # Log the raw response
            try:
                response_data = response.json()
                logger.debug(f"Parser raw response: {json.dumps(response_data, indent=2)}")
            except Exception as e:
                logger.error(f"Failed to parse response as JSON: {str(e)}")
                logger.debug(f"Parser raw response text: {response.text}")
                return None
            
            parsed_content = response_data["choices"][0]["message"]["content"]
            logger.debug(f"Parser content response: {parsed_content}")
            
            # Try to parse the JSON content
            try:
                # First attempt direct parsing
                result = json.loads(parsed_content)
                logger.info("Successfully parsed response directly with JSON")
                return result
            except json.JSONDecodeError:
                # If that fails, try to extract JSON from text (models sometimes add extra text)
                logger.warning("Direct JSON parsing failed, attempting to extract JSON from response")
                
                # Try to find JSON content using regex
                json_pattern = r'({[\s\S]*})'
                json_match = re.search(json_pattern, parsed_content)
                
                if json_match:
                    try:
                        json_content = json_match.group(1)
                        result = json.loads(json_content)
                        logger.info("Successfully extracted and parsed JSON from response text")
                        return result
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse extracted JSON: {str(e)}")
                
                # If we can't parse it as JSON, try to extract structured info from the text
                logger.warning("JSON extraction failed, parsing text response manually")
                
                # Extract thoughts
                thoughts = []
                thought_section = re.search(r'Thoughts?:?\s*\n([\s\S]*?)(?:\n\n|\Z)', parsed_content)
                if thought_section:
                    thought_lines = re.findall(r'[-•*]\s*(.*?)(?:\n|$)', thought_section.group(1))
                    thoughts = [line.strip() for line in thought_lines if line.strip()]
                
                # Extract images
                images = []
                image_section = re.search(r'Images?(?:\s*generation prompt)?:?\s*\n([\s\S]*?)(?:\n\n|\Z)', parsed_content)
                if image_section:
                    image_content = image_section.group(1).strip()
                    if image_content:
                        images = [image_content]
                
                # Extract mood
                mood = None
                mood_section = re.search(r'Mood(?:\s*update)?:?\s*\n([\s\S]*?)(?:\n\n|\Z)', parsed_content)
                if mood_section:
                    mood = mood_section.group(1).strip()
                
                # Extract main text
                main_text = response_text
                for thought in thoughts:
                    main_text = main_text.replace(f"*thought* {thought}", "")
                    main_text = main_text.replace(f"<thought>{thought}</thought>", "")
                
                if images:
                    for image in images:
                        main_text = main_text.replace(f"*image* {image}", "")
                        main_text = main_text.replace(f"<image>{image}</image>", "")
                
                if mood:
                    main_text = main_text.replace(f"*mood* {mood}", "")
                    main_text = main_text.replace(f"<mood>{mood}</mood>", "")
                
                # Clean up
                main_text = re.sub(r'\*external\*', '', main_text)
                main_text = re.sub(r'\s+', ' ', main_text).strip()
                
                result = {
                    "main_text": main_text,
                    "thoughts": thoughts,
                    "images": images,
                    "mood": mood
                }
                
                logger.info("Successfully created structured data from text response")
                return result
                
        except Exception as e:
            logger.error(f"Error in LLM parsing: {str(e)}", exc_info=True)
            return None