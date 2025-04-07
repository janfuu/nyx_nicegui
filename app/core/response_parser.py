import re
from app.models.prompt_models import PromptManager, PromptType

class ResponseParser:
    @staticmethod
    def parse_response(response_text):
        """
        Parse the LLM response to extract special tags
        """
        # Get the parsing instructions from the database
        prompt_manager = PromptManager()
        parser_data = prompt_manager.get_prompt("response_parser", PromptType.PARSER.value)
        
        if not parser_data:
            # Default parsing if not in database
            return ResponseParser._default_parse(response_text)
        
        # Extract thought tags
        thoughts = []
        thought_pattern = re.compile(r'<thought>(.*?)<\/thought>', re.DOTALL)
        for match in thought_pattern.finditer(response_text):
            thoughts.append(match.group(1).strip())
        
        # Remove thought tags from the response
        main_text = thought_pattern.sub('', response_text)
        
        # Extract image tags
        images = []
        image_pattern = re.compile(r'<image>(.*?)<\/image>', re.DOTALL)
        for match in image_pattern.finditer(main_text):
            images.append(match.group(1).strip())
        
        # Remove image tags from the response
        main_text = image_pattern.sub('', main_text)
        
        # Extract mood tag
        mood = None
        mood_pattern = re.compile(r'<mood>(.*?)<\/mood>', re.DOTALL)
        mood_match = mood_pattern.search(main_text)
        if mood_match:
            mood = mood_match.group(1).strip()
        
        # Remove mood tag from the response
        main_text = mood_pattern.sub('', main_text)
        
        # Clean up extra whitespace and line breaks
        main_text = re.sub(r'\n{3,}', '\n\n', main_text.strip())
        
        return {
            "main_text": main_text,
            "thoughts": thoughts,
            "images": images,
            "mood": mood
        }
    
    @staticmethod
    def _default_parse(response_text):
        """Default parsing method if no parser prompt is defined"""
        # Default implementation
        thoughts = []
        images = []
        mood = None
        main_text = response_text
        
        # Basic cleanup
        main_text = main_text.strip()
        
        return {
            "main_text": main_text,
            "thoughts": thoughts,
            "images": images,
            "mood": mood
        }