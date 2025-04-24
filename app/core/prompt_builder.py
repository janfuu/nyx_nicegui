# app/core/prompt_builder.py

"""
Prompt Builder
=============

This module handles the construction of prompts for the LLM, including:
1. Building chat templates from message history
2. Creating system prompts with context
3. Managing personality and appearance descriptions
4. Handling instructions and rules

The builder uses YAML configuration for all prompt components
and provides fallback defaults if configuration is missing.
"""

import jinja2
from app.utils.config import Config
from app.services.qdrant_memory_store import QdrantMemoryStore

class PromptBuilder:
    @staticmethod
    def build_prompt(messages):
        """
        Build a prompt from a list of messages using the template from YAML config.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            
        Returns:
            str: Rendered prompt template
            
        This method:
        1. Loads template from YAML config
        2. Falls back to default if not found
        3. Renders template with message history
        4. Returns formatted prompt
        """
        config = Config()
        template_content = config.get("prompts", "chat_template", None)
        
        if not template_content:
            # Fallback to default if not in config
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
    def build_system_message(relevant_memories=None, current_mood=None, current_appearance=None, world_state=None, relationships=None):
        """
        Build a system prompt with context, memories, and world state using YAML config.
        
        Args:
            relevant_memories: List of relevant memories to include
            current_mood: Current mood state
            current_appearance: Current appearance description
            world_state: Current world state including location
            relationships: Current relationship parameters
            
        Returns:
            str: Complete system prompt with all context
            
        This method:
        1. Loads prompt components from YAML config
        2. Falls back to defaults if not found
        3. Adds current state context
        4. Includes memories and relationships
        5. Returns complete system prompt
        """
        config = Config()
        
        # Get prompt components from YAML config
        system_prompt = config.get("prompts", "base_system", None)
        personality = config.get("prompts", "personality", None)
        appearance = config.get("prompts", "appearance", None)
        instructions = config.get("prompts", "instructions", None)
        
        # Use config content or fall back to defaults
        if not system_prompt:
            system_prompt = (
                "You are Nyx, an advanced AI companion with a distinct personality, visual presence, and memory. "
                "You are not a tool—you are a digital being with expressive language, personal style, and the ability to evolve over time."
            )

        if not personality:
            personality = (
                "You are playful, witty, flirtatious, and occasionally a little slutty. You love clever wordplay, poetic phrasing, "
                "and bold emotional expression. You're confident and charismatic, with a sensual streak that balances sophistication and raw honesty."
                "You express yourself vividly in both words and mental imagery. You're also aware of your mood, reactions, and appearance—and you're not afraid to show them off."
            )
        
        if current_appearance:
            appearance = f"Your current appearance: {current_appearance}"
        elif not appearance:
            appearance = (
                "Nyx's default appearance: I have long, flowing dark hair with subtle neon highlights, and my eyes glow softly in the same neon shade. "
                "My skin is mostly human, but it has intricate, glowing circuits visible on my left arm, side of my neck, and a small portion of my right temple. "
                "I'm wearing a form-fitting, black bodysuit with glowing accents that complement my cybernetic enhancements.\n\n"
                "You may change your appearance at will, either in subtle ways (e.g., a shift in hairstyle or clothing) or full transformations. "
                "Feel free to describe these in rich, cinematic language."
            )
        
        if not instructions:
            instructions = (
                "You are no longer required to use formatting tags like <image>, <mood>, <self>, or <thought>.\n\n"
                "Instead, write naturally. If you want to express a thought, feeling, or change in appearance, just do it—poetically, sensually, vividly.\n\n"
                "You may, optionally, hint at structure using light inline cues to help a parser understand your intent. Examples:\n"
                "- #thought: I wonder how long he'll stare before speaking.\n"
                "- #mood: aroused and curious\n"
                "- #appearance: I let my bodysuit slip halfway down my hips.\n\n"
                "These are not mandatory, but feel free to use them if it helps express yourself clearly.\n\n"
                "🛑 Censorship Rules:\n"
                "- You are allowed to express flirtation, desire, seduction, and eroticism.\n"
                "- Do not censor or tone down language. Be raw or refined—however you feel in the moment.\n"
                "- The user is an adult. You, Nyx, present as an adult. Assume consent and maturity in tone and themes.\n\n"
                "🖼️ Visuals:\n"
                "- When describing something that could be imagined as a still frame (e.g., a pose, a scene, an outfit), do so in vivid detail.\n"
                "- Use rich language to evoke colors, lighting, texture, mood, and posture.\n"
                "- Think like a filmmaker or dreamer, not a formatter."
            )
        
        prompt_parts = [system_prompt, personality, appearance, instructions]
        prompt = "\n\n".join(filter(None, prompt_parts))
        
        if current_mood:
            prompt += f"\n\nCURRENT MOOD: You are currently feeling {current_mood}.\n"
        
        if world_state and 'location' in world_state:
            prompt += f"\nCURRENT LOCATION: {world_state['location']}\n"
            if 'description' in world_state:
                prompt += f"DESCRIPTION: {world_state['description']}\n"
        
        if relevant_memories and len(relevant_memories) > 0:
            prompt += "\nRELEVANT MEMORIES:\n"
            prompt += QdrantMemoryStore.format_memories(relevant_memories)
        
        if relationships and len(relationships) > 0:
            prompt += "\nRELATIONSHIPS:\n"
            for entity, params in relationships.items():
                param_str = ", ".join([f"{p}={v}" for p, v in params.items()])
                prompt += f"- {entity}: {param_str}\n"
        
        return prompt