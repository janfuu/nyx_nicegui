# app/services/chat_pipeline.py

from app.core.llm_integration import LLMIntegration
from app.core.memory_system import MemorySystem
from app.core.response_parser import ResponseParser
from app.core.image_generator import ImageGenerator
from app.core.image_scene_parser import ImageSceneParser
from app.core.world_manager import WorldManager
from app.utils.config import Config
from app.utils.logger import Logger
from app.services.embedding_service import Embedder
from app.services.qdrant_memory_store import QdrantMemoryStore
from app.services.image_store import ImageStore
import time
import json
import asyncio
import uuid
import os
from PIL import Image
import io
import base64

class ResponseSession:
    def __init__(self, user_message: str):
        self.user_message = user_message
        self.streamed_tokens = []
        self.raw_response = ""
        self.parsed_content = None
        self.new_memories = []
        self.relationships = []
        self.soul_output = None
        self.generated_images = []  # Track generated images

    def append_token(self, token: str):
        self.streamed_tokens.append(token)
        self.raw_response += token

    def finalize_parsing(self, parser):
        self.parsed_content = parser(self.raw_response)
        return self.parsed_content

class ChatPipeline:
    def __init__(self):
        self.memory_system = MemorySystem()
        self.llm = LLMIntegration()
        self.world_manager = WorldManager()
        self.config = Config()
        self.logger = Logger()
        self.image_generator = ImageGenerator()
        self.image_scene_parser = ImageSceneParser()
        self.embedder = Embedder()
        self.qdrant_memory = QdrantMemoryStore()
        self.image_store = ImageStore()
    
    async def process_message(self, user_message):
        """Process a user message and generate a response with streaming support"""
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
            yield {"type": "error", "message": "I'm having trouble accessing my memories right now. Please try again."}
            return

        # Create response session
        session = ResponseSession(user_message)

        try:
            # Stream the response
            async for token in self.llm.stream_response(
                user_message=user_message,
                conversation_history=conversation_history,
                current_mood=current_mood,
                current_appearance=current_appearance[0]["description"] if current_appearance else None,
                world_state=world_state,
                relevant_memories=relevant_memories,
                relationships=relationships
            ):
                session.append_token(token)
                yield {"type": "stream", "token": token}

        except Exception as e:
            self.logger.error(f"Error in streaming response: {str(e)}")
            yield {"type": "error", "message": str(e)}
            return

        # Final parsing and post-processing
        try:
            parsed = session.finalize_parsing(self.response_parser.parse_response)
            
            # Kick off post-process tasks
            asyncio.create_task(self._post_response_processing(session))

            # Yield end-of-stream + final processed text
            yield {
                "type": "final",
                "parsed_text": parsed["main_text"],
                "mood": parsed.get("mood"),
                "tags": parsed.get("tags", []),
                "thoughts": parsed.get("thoughts", [])
            }
        except Exception as e:
            self.logger.error(f"Error in post-processing: {str(e)}")
            yield {"type": "error", "message": "Error processing the final response"}
            return

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
                
        return parsed

    async def _post_response_processing(self, session: ResponseSession):
        """Handle post-processing tasks after response streaming is complete"""
        try:
            parsed = session.parsed_content
            if not parsed:
                self.logger.error("No parsed content available for post-processing")
                return

            # Process through soul processor for memory fragments and relationships
            try:
                session.soul_output = await self.soul_processor.process(parsed)
            except Exception as e:
                self.logger.error(f"Error in soul processing: {str(e)}")
                session.soul_output = {}

            # Store new thoughts, secrets, memories, relationships
            if session.soul_output:
                try:
                    await self.memory_system.store_soul_output(session.soul_output)
                except Exception as e:
                    self.logger.error(f"Error storing soul output: {str(e)}")

            # Update mood/appearance/etc. state if changed
            if session.soul_output and "state_delta" in session.soul_output:
                try:
                    self.state_manager.apply_state_changes(session.soul_output["state_delta"])
                except Exception as e:
                    self.logger.error(f"Error applying state changes: {str(e)}")

            # Buffer surfaced memories for next turn if available
            if session.soul_output and "surfaced" in session.soul_output:
                try:
                    self.working_memory_buffer.set(session.soul_output["surfaced"])
                except Exception as e:
                    self.logger.error(f"Error buffering surfaced memories: {str(e)}")

            # Check for moment tag and store memory if present
            if parsed.get("moment"):
                try:
                    # Get current state for memory context
                    current_mood = self.memory_system.get_current_mood()
                    current_appearance = self.memory_system.get_recent_appearances(1)
                    current_appearance_text = current_appearance[0]["description"] if current_appearance else None
                    current_location = self.memory_system.get_recent_locations(1)
                    current_location_text = current_location[0]["description"] if current_location else None

                    # Create memory payload
                    memory_id = str(uuid.uuid4())
                    memory_payload = {
                        "text": parsed["moment"],
                        "type": "moment",
                        "mood": current_mood,
                        "appearance": current_appearance_text,
                        "location": current_location_text,
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                        "image_ids": [img["id"] for img in session.generated_images] if session.generated_images else []
                    }

                    # Get embedding vector
                    vector = self.embedder.embed_prompt(parsed["moment"]).tolist()

                    # Store memory in Qdrant
                    await self.qdrant_memory.store_memory(
                        memory_id=memory_id,
                        vector=vector,
                        payload=memory_payload
                    )

                    self.logger.info(f"Stored memory with moment tag: {memory_id}")
                except Exception as e:
                    self.logger.error(f"Error storing memory: {str(e)}")

            # Process any generated images
            if session.generated_images:
                try:
                    for image_data in session.generated_images:
                        # Get current state for image context
                        current_mood = self.memory_system.get_current_mood()
                        current_appearance = self.memory_system.get_recent_appearances(1)
                        current_appearance_text = current_appearance[0]["description"] if current_appearance else None
                        current_location = self.memory_system.get_recent_locations(1)
                        current_location_text = current_location[0]["description"] if current_location else None

                        # Prepare metadata
                        metadata = {
                            "prompt": image_data.get("parsed_prompt", ""),
                            "original_prompt": image_data.get("original_prompt", ""),
                            "mood": current_mood,
                            "appearance": current_appearance_text,
                            "location": current_location_text,
                            "model": "runware",
                            "rating": 0
                        }

                        # Store image using ImageStore
                        result = await self.image_store.store_image_in_qdrant(
                            image_path=image_data["file_path"],
                            image_id=image_data["id"],
                            metadata=metadata
                        )

                        if result:
                            self.logger.info(f"Stored generated image: {image_data['id']}")
                        else:
                            self.logger.error(f"Failed to store image: {image_data['id']}")
                except Exception as e:
                    self.logger.error(f"Error storing generated images: {str(e)}")

        except Exception as e:
            self.logger.error(f"Error in post-response processing: {str(e)}")
