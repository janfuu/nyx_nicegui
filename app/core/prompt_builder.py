# app/core/prompt_builder.py

import jinja2
from app.models.prompt_models import PromptManager, PromptType

class PromptBuilder:
    @staticmethod
    def build_prompt(messages):
        """Build a prompt from a list of messages using the template from database"""
        prompt_manager = PromptManager()
        template_data = prompt_manager.get_prompt("chat_template", PromptType.TEMPLATE.value)
        
        if template_data:
            template_content = template_data["content"]
        else:
            # Fallback to default if not in database
            template_content = """{% for message in messages %}
{% if message.role == 'system' %}
{{ message.content }}
{% elif message.role == 'user' %}
USER: {{ message.content }}
{% elif message.role == 'assistant' %}
ASSISTANT: {{ message.content }}
{% endif %}
{% endfor %}
ASSISTANT: """
        
        # Create a template environment with the string template
        template = jinja2.Template(template_content)
        
        # Render the template with the messages
        return template.render(messages=messages)
    
    @staticmethod
    def build_system_message(relevant_memories=None, current_mood=None, world_state=None, relationships=None):
        """Build a system prompt with context, memories, and world state using database values"""
        prompt_manager = PromptManager()
        
        # Get prompt components from database
        system_data = prompt_manager.get_prompt("base_system", PromptType.SYSTEM.value)
        personality_data = prompt_manager.get_prompt("personality", PromptType.PERSONALITY.value)
        appearance_data = prompt_manager.get_prompt("appearance", PromptType.APPEARANCE.value)
        instructions_data = prompt_manager.get_prompt("instructions", PromptType.INSTRUCTIONS.value)
        
        # Combine prompt components
        system_prompt = system_data["content"] if system_data else "You are Nyx, an AI assistant."
        personality = personality_data["content"] if personality_data else ""
        appearance = appearance_data["content"] if appearance_data else ""
        instructions = instructions_data["content"] if instructions_data else ""
        
        prompt_parts = [system_prompt, personality, appearance, instructions]
        prompt = "\n\n".join(filter(None, prompt_parts))
        
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