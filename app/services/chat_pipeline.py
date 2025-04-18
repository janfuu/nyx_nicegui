# app/services/chat_pipeline.py

from app.core.llm_integration import LLMIntegration
from app.core.memory_system import MemorySystem
from app.core.response_parser import ResponseParser
from app.core.image_generator import ImageGenerator
from app.core.image_scene_parser import ImageSceneParser
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
        self.image_scene_parser = ImageSceneParser()
        self.config = Config()
        self.logger = Logger()
    
    @staticmethod
    def _extract_image_tags(text: str) -> list[dict]:
        """Extract the content of all <image> tags from the text with sequence numbers"""
        import re
        pattern = r'<image>(.*?)</image>'
        matches = re.findall(pattern, text, re.DOTALL)
        return [{"content": match.strip(), "sequence": i+1} for i, match in enumerate(matches)]

    async def process_message(self, user_message):
        """Process a user message and generate a response"""
        self.logger.info(f"Processing message: {user_message[:50]}...")
        
        # Step 1: Get context
        self.logger.debug("Step 1: Getting context from memory system")
        conversation_history = self.memory_system.get_recent_conversation(limit=10)
        current_mood = self.memory_system.get_current_mood()
        current_appearance = self.memory_system.get_recent_appearances(1)
        world_state = self.world_manager.get_current_state()
        relevant_memories = self.memory_system.get_relevant_memories(user_message)
        relationships = self.memory_system.get_relationship_parameters()
        
        # Log context information
        self.logger.debug(f"Current mood: {current_mood}")
        self.logger.debug(f"Current appearance: {current_appearance[0]['description'] if current_appearance else 'default'}")
        self.logger.debug(f"World state: {world_state}")
        self.logger.debug(f"Found {len(relevant_memories) if relevant_memories else 0} relevant memories")
        
        # Step 2: Build system prompt
        self.logger.debug("Step 2: Building system prompt")
        system_prompt = self.llm.build_system_message(
            mood=current_mood,
            current_appearance=current_appearance[0]["description"] if current_appearance else None,
            relevant_memories=relevant_memories
        )["content"]
        
        # Step 3: Get LLM response
        self.logger.debug("Step 3: Generating LLM response")
        # Can override provider and model for main conversation
        main_provider = self.config.get("llm", "main_provider", None)  # Use default if not specified
        main_model = self.config.get("llm", "main_model", None)        # Use default if not specified
        
        llm_response = await self.llm.generate_response(
            system_prompt=system_prompt,
            user_message=user_message,
            conversation_history=conversation_history,
            provider=main_provider,
            model=main_model
        )
        
        # Step 4: Parse response for tags
        self.logger.debug("Step 4: Parsing response for special tags")
        parsed_content = ResponseParser.parse_response(
            llm_response,
            current_appearance=current_appearance[0]["description"] if current_appearance else None
        )
        
        # Log what was extracted in detail
        self.logger.debug(f"Parsed content: {json.dumps(parsed_content, indent=2)}")
        
        if parsed_content.get("thoughts"):
            self.logger.info(f"Extracted {len(parsed_content['thoughts'])} thoughts")
            for i, thought in enumerate(parsed_content['thoughts']):
                self.logger.debug(f"Thought {i+1}: {thought[:50]}...")
        
        if parsed_content.get("mood"):
            self.logger.info(f"Mood update: {parsed_content['mood']}")
        
        # Step 5: Store conversation
        self.logger.debug("Step 5: Storing conversation in memory")
        self.memory_system.add_conversation_entry("user", user_message)
        self.memory_system.add_conversation_entry("assistant", llm_response)  # Store original response
        
        # Step 6: Process response elements (thoughts, mood changes, etc.)
        self.logger.debug("Step 6: Processing extracted elements")
        
        # Process thoughts
        for thought in parsed_content.get("thoughts", []):
            self.memory_system.add_thought(thought)
            self.logger.debug(f"Added thought: {thought[:50]}...")
        
        # Process mood changes
        if parsed_content.get("mood"):
            self.memory_system.update_mood(parsed_content["mood"])
            self.logger.debug(f"Updated mood to: {parsed_content['mood']}")
        
        # Process self tags (appearance descriptions)
        if parsed_content.get("self"):
            self.logger.info(f"Extracted {len(parsed_content['self'])} self actions")
            for self_action in parsed_content["self"]:
                self.memory_system.add_appearance(self_action)
                self.logger.debug(f"Added appearance: {self_action[:50]}...")
        
        # Step 7: Generate images automatically if image tags are present
        self.logger.debug("Step 7: Checking for image tags and generating images")
        generated_images = []
        image_tags = self._extract_image_tags(llm_response)
        if image_tags:
            # Get current appearance and mood for context
            current_appearance = self.memory_system.get_recent_appearances(1)
            current_appearance_text = current_appearance[0]["description"] if current_appearance else None
            current_mood = self.memory_system.get_current_mood()
            
            # Format image contents with context and sequence
            image_context = {
                "appearance": current_appearance_text,
                "mood": current_mood,
                "images": [{"content": tag["content"], "sequence": tag["sequence"]} for tag in image_tags]
            }
            
            # Process all image tags together through the LLM-based image parser
            self.logger.info(f"Processing {len(image_tags)} image tags through image parser")
            try:
                # Use the image scene parser to generate the final image prompts
                parsed_scenes = self.image_scene_parser.parse_images(
                    json.dumps(image_context),
                    current_appearance=current_appearance_text
                )
                
                if parsed_scenes:
                    # Generate images for each parsed scene
                    for i, scene in enumerate(parsed_scenes):
                        image_url = await self.image_generator.generate(scene)
                        if image_url:
                            # Find the original sequence number for this scene
                            sequence = image_tags[i]["sequence"] if i < len(image_tags) else i + 1
                            generated_images.append({
                                "url": image_url,
                                "description": scene,
                                "id": f"img_{int(time.time())}_{i}",
                                "sequence": sequence
                            })
                            self.logger.info(f"Generated image {sequence}: {image_url}")
                        else:
                            self.logger.warning(f"Image generation failed for: {scene[:50]}...")
            except Exception as e:
                self.logger.error(f"Error processing image content: {str(e)}")
            
            # Sort images by sequence number
            generated_images.sort(key=lambda x: x["sequence"])
            self.logger.info(f"Generated {len(generated_images)} images automatically")
        
        # Return the response with images if they were generated
        self.logger.info("Message processing complete")
        return {
            "text": llm_response,  # Return original response text
            "thoughts": parsed_content.get("thoughts", []),
            "mood": parsed_content.get("mood"),
            "images": generated_images if generated_images else None
        }