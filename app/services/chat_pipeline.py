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
import asyncio

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
        try:
            conversation_history = self.memory_system.get_recent_conversation(limit=10)
            current_mood = self.memory_system.get_current_mood()
            current_appearance = self.memory_system.get_recent_appearances(1)
            world_state = self.world_manager.get_current_state()
            relevant_memories = self.memory_system.get_relevant_memories(user_message)
            relationships = self.memory_system.get_relationship_parameters()
        except Exception as e:
            self.logger.error(f"Error getting context: {str(e)}")
            return {
                "text": "I'm having trouble accessing my memories right now. Please try again.",
                "error": True
            }
        
        # Log context information
        self.logger.debug(f"Current mood: {current_mood}")
        self.logger.debug(f"Current appearance: {current_appearance[0]['description'] if current_appearance else 'default'}")
        self.logger.debug(f"World state: {world_state}")
        self.logger.debug(f"Found {len(relevant_memories) if relevant_memories else 0} relevant memories")
        
        # Step 2: Build system prompt
        self.logger.debug("Step 2: Building system prompt")
        try:
            system_prompt = self.llm.build_system_message(
                mood=current_mood,
                current_appearance=current_appearance[0]["description"] if current_appearance else None,
                relevant_memories=relevant_memories
            )["content"]
        except Exception as e:
            self.logger.error(f"Error building system prompt: {str(e)}")
            return {
                "text": "I'm having trouble organizing my thoughts right now. Please try again.",
                "error": True
            }
        
        # Step 3: Get LLM response with retries
        self.logger.debug("Step 3: Generating LLM response")
        main_provider = self.config.get("llm", "main_provider", None)
        main_model = self.config.get("llm", "main_model", None)
        
        max_retries = 3
        retry_delay = 2  # seconds
        last_error = None
        
        for attempt in range(max_retries):
            try:
                llm_response = await self.llm.generate_response(
                    system_prompt=system_prompt,
                    user_message=user_message,
                    conversation_history=conversation_history,
                    provider=main_provider,
                    model=main_model
                )
                break
            except Exception as e:
                last_error = e
                self.logger.error(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                else:
                    return {
                        "text": "I'm having trouble connecting to my thoughts right now. Please try again later.",
                        "error": True
                    }
        
        # Step 4: Parse response for tags
        self.logger.debug("Step 4: Parsing response for special tags")
        try:
            parsed_content = ResponseParser.parse_response(
                llm_response,
                current_appearance=current_appearance[0]["description"] if current_appearance else None
            )
        except Exception as e:
            self.logger.error(f"Error parsing response: {str(e)}")
            parsed_content = {"text": llm_response}  # Fallback to raw response
        
        # Log what was extracted in detail
        self.logger.debug(f"Parsed content: {json.dumps(parsed_content, indent=2)}")
        
        if parsed_content.get("thoughts"):
            self.logger.info(f"Extracted {len(parsed_content['thoughts'])} thoughts")
            for i, thought in enumerate(parsed_content['thoughts']):
                self.logger.debug(f"Thought {i+1}: {thought[:50]}...")
        
        if parsed_content.get("mood"):
            self.logger.info(f"Mood update: {parsed_content['mood']}")
            self.memory_system.update_mood(parsed_content["mood"])
        
        # Process appearance changes
        if parsed_content.get("appearance"):
            for change in parsed_content["appearance"]:
                self.memory_system.add_appearance_change(change)
            self.logger.info(f"Added {len(parsed_content['appearance'])} appearance changes")
        
        # Process location changes
        if parsed_content.get("location"):
            self.memory_system.update_location(parsed_content["location"])
            self.logger.info(f"Updated location to: {parsed_content['location']}")
        
        # Step 5: Store conversation
        self.logger.debug("Step 5: Storing conversation in memory")
        try:
            self.memory_system.add_conversation_entry("user", user_message)
            self.memory_system.add_conversation_entry("assistant", llm_response)
        except Exception as e:
            self.logger.error(f"Error storing conversation: {str(e)}")
            # Continue execution even if storage fails
        
        # Step 6: Process response elements
        self.logger.debug("Step 6: Processing extracted elements")
        try:
            # Process thoughts
            for thought in parsed_content.get("thoughts", []):
                self.memory_system.add_thought(thought)
            
            # Process self tags
            if parsed_content.get("self"):
                self.logger.info(f"Extracted {len(parsed_content['self'])} self actions")
                for self_action in parsed_content["self"]:
                    self.memory_system.add_appearance(self_action)
                    self.logger.debug(f"Added appearance: {self_action[:50]}...")
        except Exception as e:
            self.logger.error(f"Error processing response elements: {str(e)}")
            # Continue execution even if processing fails
        
        # Step 7: Generate images with timeout
        self.logger.debug("Step 7: Checking for image tags and generating images")
        generated_images = []
        image_tags = self._extract_image_tags(llm_response)
        
        if image_tags:
            try:
                current_appearance = self.memory_system.get_recent_appearances(1)
                current_appearance_text = current_appearance[0]["description"] if current_appearance else None
                current_mood = self.memory_system.get_current_mood()
                
                image_context = {
                    "appearance": current_appearance_text,
                    "mood": current_mood,
                    "images": [{"content": tag["content"], "sequence": tag["sequence"]} for tag in image_tags]
                }
                
                parsed_scenes = self.image_scene_parser.parse_images(
                    json.dumps(image_context),
                    current_appearance=current_appearance_text
                )
                
                if parsed_scenes:
                    # Generate all images in parallel
                    scene_contents = [scene['content'] if isinstance(scene, dict) else scene for scene in parsed_scenes]
                    image_urls = await asyncio.wait_for(
                        self.image_generator.generate_parallel(scene_contents),
                        timeout=90  # 90 second timeout for all images
                    )
                    
                    # Process results
                    for i, image_url in enumerate(image_urls):
                        if image_url:
                            sequence = image_tags[i]["sequence"] if i < len(image_tags) else i + 1
                            generated_images.append({
                                "url": image_url,
                                "description": scene_contents[i],
                                "id": f"img_{int(time.time())}_{i}",
                                "sequence": sequence
                            })
                
                # Sort images by sequence number
                generated_images.sort(key=lambda x: x["sequence"])
                self.logger.info(f"Generated {len(generated_images)} images in parallel")
            except Exception as e:
                self.logger.error(f"Error in image generation pipeline: {str(e)}")
        
        # Return the response with images if they were generated
        self.logger.info("Message processing complete")
        return {
            "text": llm_response,
            "thoughts": parsed_content.get("thoughts", []),
            "mood": parsed_content.get("mood"),
            "images": generated_images if generated_images else None
        }

    async def process_response(self, response_text: str) -> dict:
        """Process the response text and update memory"""
        # Parse the response
        parsed = self.response_parser.parse_response(response_text)
        
        # Update mood if present
        if parsed["mood"]:
            self.memory_system.update_mood(parsed["mood"])
            
        # Add appearance changes if present
        for change in parsed["appearance"]:
            self.memory_system.add_appearance_change(change)
            
        # Update location if present
        if parsed["location"]:
            self.memory_system.update_location(parsed["location"])
            
        # Process images if present
        if parsed["images"]:
            for image_content in parsed["images"]:
                await self.image_parser.parse_images(image_content)
                
        return parsed