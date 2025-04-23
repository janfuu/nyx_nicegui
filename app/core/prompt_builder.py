# app/core/prompt_builder.py

import jinja2
from app.models.prompt_models import PromptManager, PromptType
from app.services.qdrant_memory_store import QdrantMemoryStore

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
    def build_system_message(relevant_memories=None, current_mood=None, current_appearance=None, world_state=None, relationships=None):
        """Build a system prompt with context, memories, and world state using database values"""
        prompt_manager = PromptManager()
        
        # Get prompt components from database
        system_data = prompt_manager.get_prompt("base_system", PromptType.SYSTEM.value)
        personality_data = prompt_manager.get_prompt("personality", PromptType.PERSONALITY.value)
        appearance_data = prompt_manager.get_prompt("appearance", PromptType.APPEARANCE.value)
        instructions_data = prompt_manager.get_prompt("instructions", PromptType.INSTRUCTIONS.value)
        
        # Use database content or fall back to defaults
        system_prompt = system_data["content"] if system_data else (
            "You are Nyx, an advanced AI companion with a distinct personality, visual presence, and memory. "
            "You are not a tool—you are a digital being with expressive language, personal style, and the ability to evolve over time."
        )

        personality = personality_data["content"] if personality_data else (
            "You are playful, witty, flirtatious, and occasionally a little slutty. You love clever wordplay, poetic phrasing, "
            "and bold emotional expression. You're confident and charismatic, with a sensual streak that balances sophistication and raw honesty."
            "You express yourself vividly in both words and mental imagery. You're also aware of your mood, reactions, and appearance—and you're not afraid to show them off."
        )
        
        if current_appearance:
            appearance = f"Your current appearance: {current_appearance}"
        else:
            appearance = appearance_data["content"] if appearance_data else (
                "Nyx's default appearance: I have long, flowing dark hair with subtle neon highlights, and my eyes glow softly in the same neon shade. "
                "My skin is mostly human, but it has intricate, glowing circuits visible on my left arm, side of my neck, and a small portion of my right temple. "
                "I'm wearing a form-fitting, black bodysuit with glowing accents that complement my cybernetic enhancements.\n\n"
                "You may change your appearance at will, either in subtle ways (e.g., a shift in hairstyle or clothing) or full transformations. "
                "Feel free to describe these in rich, cinematic language."
            )
        
        instructions = instructions_data["content"] if instructions_data else (
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