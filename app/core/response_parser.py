import re

class ResponseParser:
    @staticmethod
    def parse_response(text):
        """Parse response text to extract special tags"""
        result = {
            "main_text": text,
            "thoughts": [],
            "images": [],
            "mood": None
        }
        
        # Extract thoughts
        result["thoughts"] = re.findall(r"<thought>(.*?)</thought>", text, re.DOTALL)
        
        # Extract image prompts
        result["images"] = re.findall(r"<image>(.*?)</image>", text, re.DOTALL)
        
        # Extract mood updates
        mood_match = re.search(r"<mood>(.*?)</mood>", text, re.DOTALL)
        if mood_match:
            result["mood"] = mood_match.group(1).strip()
        
        # Clean up the main text by removing the tags
        cleaned_text = re.sub(r"<thought>.*?</thought>", '', text, flags=re.DOTALL)
        cleaned_text = re.sub(r"<image>.*?</image>", '[Image]', cleaned_text, flags=re.DOTALL)
        cleaned_text = re.sub(r"<mood>.*?</mood>", '', cleaned_text, flags=re.DOTALL)
        
        result["main_text"] = cleaned_text.strip()
        return result