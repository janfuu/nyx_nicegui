import sqlite3
from enum import Enum
from app.utils.config import Config
from pathlib import Path

class PromptType(Enum):
    SYSTEM = "system"
    PERSONALITY = "personality"
    APPEARANCE = "appearance"
    INSTRUCTIONS = "instructions"
    PARSER = "parser"
    TEMPLATE = "template"

class PromptManager:
    def __init__(self):
        self.config = Config()
        db_path = Path(self.config.get("database", "path"))
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.create_tables()
        self.initialize_default_prompts()
        
    def create_tables(self):
        """Create the prompts table if it doesn't exist"""
        cursor = self.conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS prompts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            content TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        self.conn.commit()
        
    def initialize_default_prompts(self):
        """Initialize default prompts if they don't exist"""
        default_prompts = [
            {
                "name": "base_system",
                "type": PromptType.SYSTEM.value,
                "content": "You are Nyx, a curious, emotionally nuanced AI companion.",
                "description": "Base system identity"
            },
            {
                "name": "personality",
                "type": PromptType.PERSONALITY.value,
                "content": "You remember past conversations, have moods, and sometimes secrets. Speak naturally and stay in character. Avoid disclaimers.",
                "description": "Nyx's personality traits"
            },
            {
                "name": "appearance",
                "type": PromptType.APPEARANCE.value,
                "content": "You have a distinctive appearance: a futuristic woman with shimmering silver skin, chrome facial accents, dark hair. You may be visualized in images when referenced as 'me', 'myself', or similar.",
                "description": "Nyx's visual appearance"
            },
            {
                "name": "instructions",
                "type": PromptType.INSTRUCTIONS.value,
                "content": "INSTRUCTIONS:\n- Use <thought>your internal thoughts</thought> tags for things you are thinking but not saying\n- Use <image>detailed description for image generation</image> when you want to visualize something\n- Use <mood>your current emotional state</mood> to update your emotional state",
                "description": "Instructions for special tags"
            },
            {
                "name": "response_parser",
                "type": PromptType.PARSER.value,
                "content": """Parse the response to extract special tag content:

1. <thought>...</thought>: Extract internal thoughts
2. <image>...</image>: Extract image generation prompts
3. <mood>...</mood>: Extract mood updates

For each tag, extract the content and remove the tags from the main response.""",
                "description": "Instructions for parsing response tags"
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
                "description": "Template for formatting chat messages"
            }
        ]
        
        cursor = self.conn.cursor()
        for prompt in default_prompts:
            # Check if this prompt already exists
            cursor.execute("SELECT id FROM prompts WHERE name = ? AND type = ?", 
                          (prompt["name"], prompt["type"]))
            exists = cursor.fetchone()
            if not exists:
                cursor.execute("""
                INSERT INTO prompts (name, type, content, description)
                VALUES (?, ?, ?, ?)
                """, (prompt["name"], prompt["type"], prompt["content"], prompt["description"]))
        
        self.conn.commit()
    
    def get_prompt(self, name, prompt_type):
        """Get a prompt by name and type"""
        cursor = self.conn.cursor()
        cursor.execute("""
        SELECT * FROM prompts WHERE name = ? AND type = ?
        """, (name, prompt_type))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    
    def get_prompts_by_type(self, prompt_type):
        """Get all prompts of a specific type"""
        cursor = self.conn.cursor()
        cursor.execute("""
        SELECT * FROM prompts WHERE type = ?
        """, (prompt_type,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    
    def update_prompt(self, name, prompt_type, content):
        """Update a prompt's content"""
        cursor = self.conn.cursor()
        cursor.execute("""
        UPDATE prompts SET content = ?, updated_at = CURRENT_TIMESTAMP
        WHERE name = ? AND type = ?
        """, (content, name, prompt_type))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def reset_to_default(self, name, prompt_type):
        """Reset a prompt to its default value"""
        # Default values
        default_values = {
            "base_system": "You are Nyx, a curious, emotionally nuanced AI companion.",
            "personality": "You remember past conversations, have moods, and sometimes secrets. Speak naturally and stay in character. Avoid disclaimers.",
            "appearance": "You have a distinctive appearance: a futuristic woman with shimmering silver skin, chrome facial accents, dark hair. You may be visualized in images when referenced as 'me', 'myself', or similar.",
            "instructions": "INSTRUCTIONS:\n- Use <thought>your internal thoughts</thought> tags for things you are thinking but not saying\n- Use <image>detailed description for image generation</image> when you want to visualize something\n- Use <mood>your current emotional state</mood> to update your emotional state",
            "response_parser": """Parse the response to extract special tag content:

1. <thought>...</thought>: Extract internal thoughts
2. <image>...</image>: Extract image generation prompts
3. <mood>...</mood>: Extract mood updates

For each tag, extract the content and remove the tags from the main response.""",
            "chat_template": """{% for message in messages %}
{% if message.role == 'system' %}
{{ message.content }}
{% elif message.role == 'user' %}
USER: {{ message.content }}
{% elif message.role == 'assistant' %}
ASSISTANT: {{ message.content }}
{% endif %}
{% endfor %}
ASSISTANT: """
        }
        
        default_content = default_values.get(name)
        if default_content:
            return self.update_prompt(name, prompt_type, default_content)
        return False
    
    def close(self):
        """Close the database connection"""
        if self.conn:
            self.conn.close()