from enum import Enum
from app.utils.config import Config
from .database import Database

class PromptType(Enum):
    SYSTEM = "system"
    PERSONALITY = "personality"
    APPEARANCE = "appearance"
    INSTRUCTIONS = "instructions"
    PARSER = "parser"
    TEMPLATE = "template"

class PromptManager:
    def __init__(self):
        self.db = Database()
        
        # Initialize with default prompts if needed
        self.initialize_default_prompts()
    
    def get_prompt(self, name, type_value):
        """Get a prompt by name and type"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        try:
            # Try to get all fields including version
            cursor.execute(
                "SELECT name, type, content, description, version FROM prompts WHERE name = ? AND type = ?",
                (name, type_value)
            )
            
            result = cursor.fetchone()
            if result:
                return {
                    "name": result[0],
                    "type": result[1],
                    "content": result[2],
                    "description": result[3],
                    "version": result[4]
                }
        except sqlite3.OperationalError:
            # Fallback if version column doesn't exist yet
            cursor.execute(
                "SELECT name, type, content, description FROM prompts WHERE name = ? AND type = ?",
                (name, type_value)
            )
            
            result = cursor.fetchone()
            if result:
                return {
                    "name": result[0],
                    "type": result[1],
                    "content": result[2],
                    "description": result[3],
                    "version": 1  # Default version
                }
        
        return None
    
    def update_prompt(self, name, type_value, content, description=None):
        """Update a prompt in the database"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        if description:
            cursor.execute(
                """
                UPDATE prompts SET content = ?, description = ?, updated_at = CURRENT_TIMESTAMP
                WHERE name = ? AND type = ?
                """,
                (content, description, name, type_value)
            )
        else:
            cursor.execute(
                """
                UPDATE prompts SET content = ?, updated_at = CURRENT_TIMESTAMP
                WHERE name = ? AND type = ?
                """,
                (content, name, type_value)
            )
        
        if cursor.rowcount == 0:
            # Insert if it doesn't exist
            cursor.execute(
                """
                INSERT INTO prompts (name, type, content, description, is_default) 
                VALUES (?, ?, ?, ?, 0)
                """,
                (name, type_value, content, description)
            )
        
        conn.commit()
        return True
    
    def update_prompt_with_version(self, name, type_value, content, version, description=None):
        """Update a prompt with version tracking"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        # First check if it exists and what version it is
        cursor.execute(
            "SELECT version, is_default FROM prompts WHERE name = ? AND type = ?",
            (name, type_value)
        )
        
        result = cursor.fetchone()
        
        if result:
            current_version, is_default = result
            
            # Only update if it's a default prompt or the version is older
            if is_default == 1 or current_version < version:
                if description:
                    cursor.execute(
                        """
                        UPDATE prompts SET 
                        content = ?, 
                        description = ?, 
                        version = ?,
                        updated_at = CURRENT_TIMESTAMP
                        WHERE name = ? AND type = ?
                        """,
                        (content, description, version, name, type_value)
                    )
                else:
                    cursor.execute(
                        """
                        UPDATE prompts SET 
                        content = ?, 
                        version = ?,
                        updated_at = CURRENT_TIMESTAMP
                        WHERE name = ? AND type = ?
                        """,
                        (content, version, name, type_value)
                    )
        else:
            # Insert new prompt with version
            cursor.execute(
                """
                INSERT INTO prompts (name, type, content, description, version, is_default) 
                VALUES (?, ?, ?, ?, ?, 1)
                """,
                (name, type_value, content, description, version)
            )
        
        conn.commit()
        return True
    
    def reset_to_default(self, name, type_value):
        """Reset a prompt to its default value"""
        # First, we'll get all default prompts and find the matching one
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        # Reset by name and type
        cursor.execute(
            """
            UPDATE prompts SET is_default = 1
            WHERE name = ? AND type = ?
            """,
            (name, type_value)
        )
        
        # Also trigger default initialization
        self.initialize_default_prompts()
        
        conn.commit()
        return True
    
    def initialize_default_prompts(self):
        """Initialize default prompts if they don't exist"""
        default_prompts = [
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
            },
            {
                "name": "response_parser",
                "type": PromptType.PARSER.value,
                "content": """You are a JSON parser that extracts structured information from AI responses.
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
RETURN ONLY THE JSON OBJECT.""",
                "description": "Instructions for parsing response tags",
                "version": 1
            }
        ]
        
        for prompt in default_prompts:
            # Check if prompt exists
            existing = self.get_prompt(prompt["name"], prompt["type"])
            
            if not existing:
                # Insert default prompt
                self.update_prompt_with_version(
                    prompt["name"], 
                    prompt["type"], 
                    prompt["content"], 
                    prompt["version"],
                    prompt["description"]
                )