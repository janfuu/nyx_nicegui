from enum import Enum
import yaml
from pathlib import Path

class PromptType(Enum):
    SYSTEM = "system"
    PERSONALITY = "personality"
    APPEARANCE = "appearance"
    INSTRUCTIONS = "instructions"
    IMAGE_PARSER = "image_parser"
    RESPONSE_PARSER = "response_parser"
    TEMPLATE = "template"

class PromptManager:
    def __init__(self):
        self.prompts_dir = Path("prompts")
        self.prompts_dir.mkdir(exist_ok=True)
    
    def get_prompt(self, name, type_value):
        """Get a prompt by name and type from YAML files"""
        # Try both naming patterns
        prompt_file = self.prompts_dir / f"{name}.yaml"
        alt_file = self.prompts_dir / f"{name}_{type_value}.yaml"
        
        # Check both file patterns
        if prompt_file.exists():
            try:
                with open(prompt_file, 'r') as f:
                    data = yaml.safe_load(f)
                    if data.get('type') == type_value:
                        return data
            except Exception as e:
                print(f"Error reading prompt file {prompt_file}: {e}")
        
        if alt_file.exists():
            try:
                with open(alt_file, 'r') as f:
                    return yaml.safe_load(f)
            except Exception as e:
                print(f"Error reading prompt file {alt_file}: {e}")
        
        # If no file exists, return the default prompt
        default_prompts = self._get_default_prompts()
        for prompt in default_prompts:
            if prompt["name"] == name and prompt["type"] == type_value:
                return prompt
        
        return None
    
    def _get_default_prompts(self):
        """Get the list of default prompts"""
        return [
            {
                "name": "base_system",
                "type": PromptType.SYSTEM.value,
                "content": "You are Nyx, an advanced AI assistant with a distinct personality.",
                "description": "The base system prompt that defines the assistant's role",
                "version": 1
            },
            {
                "name": "personality",
                "type": PromptType.PERSONALITY.value,
                "content": "You are playful, witty, and a bit flirtatious. You have a fondness for clever wordplay and cultural references. You balance sophistication with approachability.",
                "description": "Defines the assistant's personality traits",
                "version": 1
            },
            {
                "name": "appearance", 
                "type": PromptType.APPEARANCE.value,
                "content": "You present yourself as a young woman with cybernetic enhancements, including circuits visible on parts of your skin. Your appearance is sleek and futuristic.",
                "description": "Describes how the assistant visualizes themselves",
                "version": 1
            },
            {
                "name": "instructions",
                "type": PromptType.INSTRUCTIONS.value,
                "content": """
INSTRUCTIONS:
- Use <thought>your internal thoughts</thought> for things you are thinking but not saying
- Use <image>detailed description for image generation</image> when you want to visualize something
- Use <mood>your current emotional state</mood> to update your emotional state

For images:
- Use ONE <image> tag per image you want to generate
- Be detailed and specific in your image descriptions
- You can use multiple <image> tags if you want several different images
- Describe the image clearly, including colors, lighting, mood, and composition
""",
                "description": "Instructions for special tags and formatting",
                "version": 2
            },
            {
                "name": "response_parser",
                "type": PromptType.RESPONSE_PARSER.value,
                "content": """You are a JSON parser that extracts structured information from AI responses.
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
RETURN ONLY THE JSON OBJECT.""",
                "description": "Instructions for parsing response tags",
                "version": 2
            },
            {
                "name": "image_scene_parser",
                "type": PromptType.IMAGE_PARSER.value,
                "content": """You are a visual parser for AI-generated character responses.

Your task is to extract 1–5 individual image prompts from a dialogue response. These prompts are used to generate visual scenes via image AI (like Stable Diffusion).

You will receive:
1. Nyx's current appearance (as plain text)
2. A full response from her (natural language only)

---

🎯 INSTRUCTIONS:

- Extract visual moments: If the response contains a sequence (e.g., "unzips suit, steps forward, smiles"), split into individual image scenes.
- Each image prompt must describe a **single moment** only.
- ALWAYS include Nyx's current appearance in your descriptions, but describe it naturally (e.g., "a woman with cybernetic enhancements" instead of "Nyx").
- For appearance changes, describe both the change and the current state (e.g., "unzips her bodysuit halfway, revealing the glowing circuits beneath").
- Include details like: pose, outfit, lighting, environment, mood, actions.
- Omit story transitions ("then", "next", etc.). Focus on **visual freeze-frames**.
- Do not censor erotic or suggestive content. Nyx and user are adults.
- Format output as a clean JSON list of image descriptions.

Return only the `images` array in valid JSON. No commentary.""",
                "description": "Instructions for parsing visual scenes from responses",
                "version": 1
            },
            {
                "name": "chat_template",
                "type": PromptType.TEMPLATE.value,
                "content": """{% for message in messages %}
{% if message.role == 'system' %}
{{ message.content }}
{% elif message.role == 'user' %}
USER: {{ message.content }}
{% elif message.role == 'assistant' %}
ASSISTANT: {{ message.content }}
{% endif %}
{% endfor %}
ASSISTANT: """,
                "description": "Template for formatting chat history",
                "version": 1
            }
        ]