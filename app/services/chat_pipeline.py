# app/services/chat_pipeline.py

"""
Chat Pipeline Service
====================

This module implements the core chat processing pipeline that handles:
1. Message processing and response generation
2. Memory management and context retrieval
3. Image generation and storage
4. State management and updates

The pipeline orchestrates various components (LLM, memory system, image generation, etc.)
to provide a cohesive chat experience with memory, context, and multimedia capabilities.

Key Components:
- ResponseSession: Tracks the state of a single chat response
- ChatPipeline: Main orchestrator that processes messages and manages the chat flow
"""

from app.core.llm_integration import LLMIntegration
from app.core.memory_system import MemorySystem
from app.core.response_parser import ResponseParser
from app.core.image_generator import ImageGenerator
from app.core.image_scene_parser import ImageSceneParser
from app.core.world_manager import WorldManager
from app.utils.config import Config
from app.utils.logger import Logger
from app.services.embedder import get_embedder
from app.services.qdrant_memory_store import QdrantMemoryStore
from app.services.store_images import StoreImages
import time
import json
import asyncio
import uuid
import os
from PIL import Image
import io
import base64

class ResponseSession:
    """
    Tracks the state and content of a single chat response session.
    
    This class maintains the complete context of a response being generated,
    including the raw tokens, parsed content, and any associated images or memories.
    It's used to ensure all components of a response (text, images, memories) stay
    synchronized throughout the processing pipeline.
    """
    def __init__(self, user_message: str):
        self.user_message = user_message
        self.streamed_tokens = []  # Individual tokens as they're streamed
        self.raw_response = ""     # Complete response text
        self.parsed_content = None # Parsed response structure
        self.new_memories = []     # New memories to be stored
        self.relationships = []    # Relationship updates
        self.soul_output = None    # Output from soul processor
        self.generated_images = [] # Images generated during response

    def append_token(self, token: str):
        """
        Add a new token to the response stream.
        
        This method maintains both the token-by-token history and the complete
        response text, enabling both streaming and complete response processing.
        """
        self.streamed_tokens.append(token)
        self.raw_response += token

    def finalize_parsing(self, parser):
        """
        Parse the complete response using the provided parser.
        
        This method is called after all tokens have been received to convert
        the raw response into a structured format that can be processed further.
        """
        self.parsed_content = parser(self.raw_response)
        return self.parsed_content

class ChatPipeline:
    """
    Main chat processing pipeline that orchestrates all components.
    
    This class is responsible for:
    1. Processing user messages and generating responses
    2. Managing context and memory retrieval
    3. Handling image generation and storage
    4. Updating system state and storing memories
    5. Coordinating all components in the correct sequence
    
    The pipeline ensures that all components work together to provide a
    coherent chat experience with memory, context, and multimedia capabilities.
    """
    def __init__(self):
        self.memory_system = MemorySystem()      # Handles memory storage and retrieval
        self.llm = LLMIntegration()              # Language model interface
        self.world_manager = WorldManager()      # Manages world state and context
        self.config = Config()                   # Configuration management
        self.logger = Logger()                   # Logging system
        self.image_generator = ImageGenerator()  # Image generation service
        self.image_scene_parser = ImageSceneParser() # Parses image generation requests
        self.embedder = get_embedder()               # Text embedding service
        self.qdrant_memory = QdrantMemoryStore() # Vector memory storage
        self.image_store = StoreImages()          # Image storage service
    
    async def process_message(self, user_message):
        """
        Process a user message and generate a streaming response.
        
        This is the main entry point for chat processing. It:
        1. Retrieves relevant context and memories
        2. Streams the response from the LLM
        3. Handles post-processing and memory storage
        4. Manages image generation and storage
        
        The method yields streaming updates that can be sent to the client
        in real-time, including tokens, final response, and any errors.
        """
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
        """
        Process a response text and update system state.
        
        This method handles the post-processing of a response, including:
        1. Parsing the response into structured data
        2. Updating mood state
        3. Processing appearance changes
        4. Updating location information
        
        Returns the parsed response structure for further processing.
        """
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
        """
        Handle all post-processing tasks after response generation.
        
        This method manages the complex post-processing pipeline:
        1. Processes the response through the soul processor
        2. Stores new memories and relationships
        3. Updates system state
        4. Handles moment tagging and memory storage
        5. Processes and stores generated images
        
        All operations are wrapped in try-except blocks to ensure
        failures in one component don't affect others.
        """
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

            # Store thoughts, secrets, and fantasies from soul output
            if session.soul_output:
                try:
                    # Store thoughts
                    for thought in session.soul_output.get("thoughts", []):
                        await self.memory_system.add_thought(
                            content=thought["content"],
                            intensity=thought.get("intensity", 0.5)
                        )
                        
                    # Store secrets
                    for secret in session.soul_output.get("secrets", []):
                        await self.memory_system.add_secret(
                            content=secret["content"],
                            intensity=secret.get("intensity", 0.5)
                        )
                        
                    # Store fantasies
                    for fantasy in session.soul_output.get("fantasies", []):
                        await self.memory_system.add_fantasy(
                            content=fantasy["content"],
                            intensity=fantasy.get("intensity", 0.5)
                        )
                except Exception as e:
                    self.logger.error(f"Error storing mental states: {str(e)}")

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
                    # Get current state from state manager
                    current_state = self.state_manager.get_state()
                    
                    # Create memory payload
                    memory_id = str(uuid.uuid4())
                    memory_payload = {
                        "text": parsed["moment"],
                        "type": "moment",
                        "mood": current_state.get("mood"),
                        "appearance": current_state.get("appearance"),
                        "location": current_state.get("location"),
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                        "image_ids": [img["id"] for img in session.generated_images] if session.generated_images else [],
                        "intensity": parsed.get("intensity", 0.5)
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
                    # Get current state from state manager
                    current_state = self.state_manager.get_state()
                    
                    for image_data in session.generated_images:
                        # Prepare metadata
                        metadata = {
                            "prompt": image_data.get("parsed_prompt", ""),
                            "original_prompt": image_data.get("original_prompt", ""),
                            "mood": current_state.get("mood"),
                            "appearance": current_state.get("appearance"),
                            "location": current_state.get("location"),
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
