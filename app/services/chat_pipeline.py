# app/services/chat_pipeline.py

from app.core.llm_integration import LLMIntegration
from app.core.memory_system import MemorySystem
from app.core.response_parser import ResponseParser
from app.core.image_generator import ImageGenerator
from app.core.world_manager import WorldManager
from app.utils.config import Config

class ChatPipeline:
    def __init__(self):
        self.memory_system = MemorySystem()
        self.llm = LLMIntegration()
        self.world_manager = WorldManager()
        self.image_generator = ImageGenerator()
        self.config = Config()
    
    def process_message(self, user_message):
        """Process a user message and generate a response"""
        # Step 1: Get context
        conversation_history = self.memory_system.get_recent_conversation(limit=10)
        current_mood = self.memory_system.get_current_mood()
        world_state = self.world_manager.get_current_state()
        relevant_memories = self.memory_system.get_relevant_memories(user_message)
        relationships = self.memory_system.get_relationship_parameters()
        
        # Step 2: Build system prompt
        system_prompt = self.llm.build_system_message(
            mood=current_mood,
            relevant_memories=relevant_memories
        )["content"]
        
        # Step 3: Get LLM response
        # Can override provider and model for main conversation
        main_provider = self.config.get("llm", "main_provider", None)  # Use default if not specified
        main_model = self.config.get("llm", "main_model", None)        # Use default if not specified
        
        llm_response = self.llm.generate_response(
            system_prompt=system_prompt,
            user_message=user_message,
            conversation_history=conversation_history,
            provider=main_provider,
            model=main_model
        )
        
        # Step 4: Parse response
        parsed_response = ResponseParser.parse_response(llm_response)
        
        # Step 5: Store conversation
        self.memory_system.add_conversation_entry("user", user_message)
        self.memory_system.add_conversation_entry("assistant", parsed_response["main_text"])
        
        # Step 6: Process special content
        
        # Store thoughts
        for thought in parsed_response["thoughts"]:
            self.memory_system.add_thought(thought)
        
        # Update mood if provided
        if parsed_response["mood"]:
            self.memory_system.update_mood(parsed_response["mood"])
        
        # Generate images if requested
        images = []
        for image_prompt in parsed_response["images"]:
            image_url = self.image_generator.generate(image_prompt)
            if image_url:
                images.append({"prompt": image_prompt, "url": image_url})
        
        # Step 7: Prepare response
        return {
            "text": parsed_response["main_text"],
            "thoughts": parsed_response["thoughts"],
            "mood": parsed_response["mood"] or current_mood,
            "images": images
        }