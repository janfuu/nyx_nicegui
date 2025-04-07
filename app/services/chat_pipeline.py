# app/services/chat_pipeline.py

from app.core.llm_integration import LLMIntegration
from app.core.memory_system import MemorySystem
from app.core.response_parser import ResponseParser
from app.core.image_generator import ImageGenerator
from app.core.world_manager import WorldManager
from app.utils.config import Config
from app.utils.logger import Logger
import time
import json

class ChatPipeline:
    def __init__(self):
        self.memory_system = MemorySystem()
        self.llm = LLMIntegration()
        self.world_manager = WorldManager()
        self.image_generator = ImageGenerator()
        self.config = Config()
        self.logger = Logger()
    
    def process_message(self, user_message):
        """Process a user message and generate a response"""
        self.logger.info(f"Processing message: {user_message[:50]}...")
        
        # Step 1: Get context
        self.logger.debug("Step 1: Getting context from memory system")
        conversation_history = self.memory_system.get_recent_conversation(limit=10)
        current_mood = self.memory_system.get_current_mood()
        world_state = self.world_manager.get_current_state()
        relevant_memories = self.memory_system.get_relevant_memories(user_message)
        relationships = self.memory_system.get_relationship_parameters()
        
        # Log context information
        self.logger.debug(f"Current mood: {current_mood}")
        self.logger.debug(f"World state: {world_state}")
        self.logger.debug(f"Found {len(relevant_memories) if relevant_memories else 0} relevant memories")
        
        # Step 2: Build system prompt
        self.logger.debug("Step 2: Building system prompt")
        system_prompt = self.llm.build_system_message(
            mood=current_mood,
            relevant_memories=relevant_memories
        )["content"]
        
        # Step 3: Get LLM response
        self.logger.debug("Step 3: Generating LLM response")
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
        self.logger.debug("Step 4: Parsing response for special tags")
        parsed_response = ResponseParser.parse_response(llm_response)
        
        # Log what was extracted in detail
        self.logger.debug(f"Parsed response: {json.dumps(parsed_response, indent=2)}")
        
        if parsed_response.get("thoughts"):
            self.logger.info(f"Extracted {len(parsed_response['thoughts'])} thoughts")
            for i, thought in enumerate(parsed_response['thoughts']):
                self.logger.debug(f"Thought {i+1}: {thought[:50]}...")
        
        if parsed_response.get("images"):
            self.logger.info(f"Extracted {len(parsed_response['images'])} image requests")
            for i, img in enumerate(parsed_response['images']):
                self.logger.debug(f"Image {i+1}: {img[:50]}...")
        
        if parsed_response.get("mood"):
            self.logger.info(f"Mood update: {parsed_response['mood']}")
        
        # Step 5: Store conversation
        self.logger.debug("Step 5: Storing conversation in memory")
        self.memory_system.add_conversation_entry("user", user_message)
        self.memory_system.add_conversation_entry("assistant", parsed_response["main_text"])
        
        # Step 6: Process response elements (thoughts, mood changes, etc.)
        self.logger.debug("Step 6: Processing extracted elements")
        
        # Process thoughts
        for thought in parsed_response.get("thoughts", []):
            self.memory_system.add_thought(thought)
            self.logger.debug(f"Added thought: {thought[:50]}...")
        
        # Process mood changes
        if parsed_response.get("mood"):
            self.memory_system.update_mood(parsed_response["mood"])
            self.logger.debug(f"Updated mood to: {parsed_response['mood']}")
        
        # Process image generation with descriptions
        image_results = []
        for i, image_prompt in enumerate(parsed_response.get("images", [])):
            self.logger.info(f"Generating image for: {image_prompt[:50]}...")
            try:
                image_url = self.image_generator.generate(image_prompt)
                if image_url:
                    # Store both the URL and the original description
                    image_results.append({
                        "url": image_url,
                        "description": image_prompt,
                        "id": f"img_{int(time.time())}_{i}"  # Unique ID for reference
                    })
                    self.logger.info(f"Generated image: {image_url}")
                else:
                    self.logger.warning(f"Failed to generate image for: {image_prompt[:50]}...")
            except Exception as e:
                self.logger.error(f"Error generating image: {str(e)}")
        
        # Return both the text response and any generated images
        self.logger.info("Message processing complete")
        return {
            "text": parsed_response["main_text"],
            "images": image_results,
            "thoughts": parsed_response.get("thoughts", []),
            "mood": parsed_response.get("mood")
        }