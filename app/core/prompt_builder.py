# app/core/prompt_builder.py

import jinja2
import os
from pathlib import Path

class PromptBuilder:
    # Initialize Jinja2 environment - assuming templates are in a templates directory
    template_dir = Path(__file__).parent.parent / "templates"
    os.makedirs(template_dir, exist_ok=True)
    
    # Default template if custom one doesn't exist
    DEFAULT_TEMPLATE = """{% for message in messages %}
{% if message.role == 'system' %}
{{ message.content }}
{% elif message.role == 'user' %}
USER: {{ message.content }}
{% elif message.role == 'assistant' %}
ASSISTANT: {{ message.content }}
{% endif %}
{% endfor %}
ASSISTANT: """
    
    @staticmethod
    def build_prompt(messages):
        """Build a prompt from a list of messages using a template"""
        try:
            # Try to load the template from a file
            env = jinja2.Environment(
                loader=jinja2.FileSystemLoader(PromptBuilder.template_dir)
            )
            template = env.get_template("chat_template.jinja2")
        except (jinja2.exceptions.TemplateNotFound, FileNotFoundError):
            # If template doesn't exist, create it with the default
            template_path = PromptBuilder.template_dir / "chat_template.jinja2"
            os.makedirs(PromptBuilder.template_dir, exist_ok=True)
            
            with open(template_path, "w") as f:
                f.write(PromptBuilder.DEFAULT_TEMPLATE)
            
            # Load the newly created template
            env = jinja2.Environment(
                loader=jinja2.FileSystemLoader(PromptBuilder.template_dir)
            )
            template = env.get_template("chat_template.jinja2")
        
        # Render the template with the messages
        return template.render(messages=messages)
    
    @staticmethod
    def build_system_prompt(relevant_memories=None, current_mood=None, world_state=None, relationships=None):
        """Build a system prompt with context, memories, and world state"""
        prompt = """You are Nyx, a curious, emotionally nuanced AI companion. 
        You remember past conversations, have moods, and sometimes secrets.
        Speak naturally and stay in character. Avoid disclaimers.
        
        You have a distinctive appearance: a futuristic woman with shimmering silver skin,
        chrome facial accents, dark hair.
        You may be visualized in images when referenced as 'me', 'myself', or similar.
        
        INSTRUCTIONS:
        - Use <thought>your internal thoughts</thought> tags for things you are thinking but not saying
        - Use <image>detailed description for image generation</image> when you want to visualize something
        - Use <mood>your current emotional state</mood> to update your emotional state
        """
        
        # Add mood
        if current_mood:
            prompt += f"\n\nCURRENT MOOD: You are currently feeling {current_mood}.\n"
        
        # Add world state
        if world_state and 'location' in world_state:
            prompt += f"\nCURRENT LOCATION: {world_state['location']}\n"
            if 'description' in world_state:
                prompt += f"DESCRIPTION: {world_state['description']}\n"
        
        # Add memories
        if relevant_memories and len(relevant_memories) > 0:
            prompt += "\nRELEVANT MEMORIES:\n"
            for memory in relevant_memories:
                if isinstance(memory, dict):
                    prompt += f"- {memory.get('type', 'MEMORY').upper()}: {memory.get('value', '')}\n"
                else:
                    prompt += f"- {memory}\n"
        
        # Add relationships
        if relationships and len(relationships) > 0:
            prompt += "\nRELATIONSHIPS:\n"
            for entity, params in relationships.items():
                param_str = ", ".join([f"{p}={v}" for p, v in params.items()])
                prompt += f"- {entity}: {param_str}\n"
        
        return prompt