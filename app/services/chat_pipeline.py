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
    
    async def process_message(self, user_message):
        """Process a user message and generate a response"""
        self.logger.info(f"Processing message: {user_message[:50]}...")
        
        # Step 1: Get context
        try:
            conversation_history = self.memory_system.get_recent_conversation(limit=20)
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
        
        # Step 2: Build system prompt
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
        try:
            parsed_content = await ResponseParser._llm_parse(
                llm_response,
                current_appearance=current_appearance[0]["description"] if current_appearance else None
            )
            if not parsed_content:
                self.logger.error("LLM parser failed to parse response")
                return {
                    "text": "I'm having trouble processing my response. Please try again.",
                    "error": True
                }
        except Exception as e:
            self.logger.error(f"Error parsing response: {str(e)}")
            return {
                "text": "I'm having trouble processing my response. Please try again.",
                "error": True
            }
        
        # Store semantic memories
        try:
            mood = parsed_content.get("mood")
            mood_vector = None
            if mood:
                mood_vector = self.embedder.embed_prompt(mood).tolist()
            moment_memory_id = None  # Track the moment memory ID if we store one
            
            # Store thoughts
            for thought in parsed_content.get("thoughts", []):
                await self.qdrant_memory.store_memory(
                    text=thought,
                    vector=self.embedder.embed_prompt(thought).tolist(),
                    memory_type="thought",
                    mood=mood,
                    mood_vector=mood_vector,
                    tags=["thought"]
                )
            
            # Store secrets
            for secret in parsed_content.get("secret", []):
                await self.qdrant_memory.store_memory(
                    text=secret,
                    vector=self.embedder.embed_prompt(secret).tolist(),
                    memory_type="secret",
                    mood=mood,
                    mood_vector=mood_vector,
                    tags=["secret"]
                )
            
            # Store moments
            if parsed_content.get("moment") is not None:
                main_text = parsed_content.get("main_text")
                if main_text:
                    moment_memory_id = await self.qdrant_memory.store_memory(
                        text=main_text,
                        vector=self.embedder.embed_prompt(main_text).tolist(),
                        memory_type="moment",
                        mood=mood,
                        mood_vector=mood_vector,
                        tags=["moment"]
                    )
        except Exception as e:
            self.logger.error(f"Error storing semantic memories: {str(e)}")
            # Continue execution even if memory storage fails
        
        # Process mood and appearance changes
        if parsed_content.get("mood"):
            self.memory_system.update_mood(parsed_content["mood"])
            self.logger.info(f"Mood update: {parsed_content['mood']}")
        
        if parsed_content.get("appearance"):
            for change in parsed_content["appearance"]:
                self.memory_system.add_appearance(change)
            self.logger.info(f"Added {len(parsed_content['appearance'])} appearance changes")
        
        if parsed_content.get("clothing"):
            for change in parsed_content["clothing"]:
                self.memory_system.add_clothing(change)
            self.logger.info(f"Added {len(parsed_content['clothing'])} clothing changes")
        
        if parsed_content.get("location"):
            self.memory_system.update_location(parsed_content["location"])
            self.logger.info(f"Updated location to: {parsed_content['location']}")
        
        # Step 5: Store conversation
        try:
            self.memory_system.add_conversation_entry("user", user_message)
            self.memory_system.add_conversation_entry("assistant", parsed_content["main_text"])
        except Exception as e:
            self.logger.error(f"Error storing conversation: {str(e)}")
        
        # Step 6: Process response elements
        try:
            for thought in parsed_content.get("thoughts", []):
                self.memory_system.add_thought(thought)
        except Exception as e:
            self.logger.error(f"Error processing response elements: {str(e)}")
        
        # Step 7: Generate images with timeout
        generated_images = []
        
        if parsed_content.get("images"):
            try:
                current_appearance = self.memory_system.get_recent_appearances(1)
                current_appearance_text = current_appearance[0]["description"] if current_appearance else None
                current_mood = self.memory_system.get_current_mood()
                current_location = self.memory_system.get_recent_locations(1)
                current_location_text = current_location[0]["description"] if current_location else None
                current_clothing = self.memory_system.get_recent_clothing(1)
                current_clothing_text = current_clothing[0]["description"] if current_clothing else None
                
                image_context = {
                    "appearance": current_appearance_text,
                    "mood": current_mood,
                    "clothing": current_clothing_text,
                    "location": current_location_text,
                    "images": [{"content": content, "sequence": i+1} for i, content in enumerate(parsed_content["images"])]
                }
                
                parsed_scenes = await self.image_scene_parser.parse_images(
                    json.dumps(image_context),
                    current_appearance=current_appearance_text
                )
                
                if parsed_scenes:
                    scene_contents = []
                    for scene in parsed_scenes:
                        if isinstance(scene, dict) and ('content' in scene or 'prompt' in scene):
                            scene_contents.append(scene)
                        else:
                            scene_contents.append({
                                "prompt": scene if isinstance(scene, str) else str(scene),
                                "orientation": "portrait"
                            })
                    
                    image_urls = await self.image_generator.generate(scene_contents)
                    
                    for i, image_url in enumerate(image_urls):
                        if image_url:
                            sequence = scene_contents[i].get("frame", i + 1)
                            try:
                                image_uuid = image_url.split('/')[-1].split('.')[0]
                            except:
                                image_uuid = f"img_{int(time.time())}_{i}"
                            
                            original_prompt = ""
                            if i < len(parsed_content["images"]):
                                original_prompt = parsed_content["images"][i]
                            
                            generated_images.append({
                                "url": image_url,
                                "description": scene_contents[i].get("content", scene_contents[i].get("prompt", "Generated image")),
                                "id": image_uuid,
                                "sequence": sequence,
                                "original_prompt": original_prompt,
                                "parsed_prompt": scene_contents[i].get("prompt", "")
                            })
                            
                            scene_data = scene_contents[i].copy() if isinstance(scene_contents[i], dict) else {"prompt": scene_contents[i]}
                            scene_data["original_content"] = scene_contents[i].get("original_text", "")
                            
                            asyncio.create_task(
                                self._process_image_for_qdrant(
                                    scene_data=scene_data,
                                    image_url=image_url,
                                    mood=current_mood,
                                    appearance=current_appearance_text,
                                    location=current_location_text,
                                    image_id=image_uuid
                                )
                            )
                
                generated_images.sort(key=lambda x: x["sequence"])
                self.logger.info(f"Generated {len(generated_images)} images")
                
                # If we stored a moment memory, update it with the image IDs
                if moment_memory_id:
                    try:
                        # Only update if we have images
                        if generated_images:
                            # Use the same image_uuid that will be used for Qdrant storage
                            image_ids = [img["id"] for img in generated_images]
                            await self.qdrant_memory.update_memory(
                                memory_id=moment_memory_id,
                                image_ids=image_ids
                            )
                            self.logger.info(f"Updated moment memory {moment_memory_id} with {len(image_ids)} image IDs")
                        else:
                            self.logger.info(f"No images to associate with moment memory {moment_memory_id}")
                    except Exception as e:
                        self.logger.error(f"Error updating moment memory with image IDs: {str(e)}")
            except Exception as e:
                self.logger.error(f"Error in image generation pipeline: {str(e)}")
        
        return {
            "text": parsed_content["main_text"],
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
                await self.image_scene_parser.parse_images(image_content)
                
        return parsed
    
    async def _process_image_for_qdrant(self, scene_data, image_url, mood, appearance, location, image_id):
        try:
            self.logger.info(f"[Qdrant] Starting image processing for {image_id}")
            from app.main import get_embedder
            from app.services.qdrant_client import QdrantImageStore

            embedder = get_embedder()
            qdrant = QdrantImageStore()
            
            # Get the current clothing from memory system
            clothing = None
            try:
                current_clothing = self.memory_system.get_recent_clothing(1)
                clothing = current_clothing[0]["description"] if current_clothing else None
            except Exception as e:
                self.logger.error(f"[Qdrant] Error getting clothing: {str(e)}")
            
            self.logger.info(f"[Qdrant] Embedding image from URL: {image_url}")
            image_vector, thumbnail_b64 = embedder.embed_image_from_url(image_url)
            self.logger.info(f"[Qdrant] Image embedding completed successfully: {image_vector is not None}")
            
            # Get the prompt
            parsed_prompt = scene_data.get("prompt", "")
            # Get the original prompt if available
            original_prompt = scene_data.get("original_content", "")
            if not original_prompt and "content" in scene_data:
                original_prompt = scene_data.get("content", "")
            
            self.logger.info(f"[Qdrant] Embedding prompt: {parsed_prompt[:30]}...")
            prompt_vector = embedder.embed_prompt(parsed_prompt)
            self.logger.info(f"[Qdrant] Prompt embedding completed successfully: {prompt_vector is not None}")

            if image_vector is not None and prompt_vector is not None:
                self.logger.info(f"[Qdrant] Preparing payload for storage")
                payload = {
                    "prompt": parsed_prompt,
                    "original_prompt": original_prompt,
                    "url": image_url,
                    "thumbnail_b64": thumbnail_b64,
                    "mood": mood,
                    "appearance": appearance,
                    "clothing": clothing,
                    "location": location,
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "model": "runware",
                    "rating": 0
                }
                
                self.logger.info(f"[Qdrant] Storing image {image_id} in Qdrant")
                result = await qdrant.store_image_embedding(
                    image_id=image_id,
                    vector=image_vector.tolist(),
                    payload=payload
                )
                self.logger.info(f"[Qdrant] Storage completed with result: {result}")
            else:
                self.logger.error(f"[Qdrant] Failed to create embeddings: image_vector={image_vector is not None}, prompt_vector={prompt_vector is not None}")
        except Exception as e:
            self.logger.error(f"[Qdrant] Failed to process image: {e}")
            import traceback
            self.logger.error(f"[Qdrant] Traceback: {traceback.format_exc()}")
