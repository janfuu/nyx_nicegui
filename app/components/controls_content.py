"""
Controls Content Component
=========================

This module serves as a testing and control interface for various system components.
It provides:
1. Image generation and rating interface
2. Memory system testing tools
3. System state inspection
4. Diagnostic utilities

The component is primarily used for development and testing, allowing direct
interaction with core system features and manual verification of functionality.

WARNING: This is a complex testing environment with many interdependencies.
Be extremely careful when modifying any async operations or UI state management.
"""

from nicegui import ui, app, events
from app.models.prompt_models import PromptManager, PromptType
from app.core.memory_system import MemorySystem
from app.core.prompt_builder import PromptBuilder
from functools import partial
import json
import os
from pathlib import Path
from app.core.image_scene_parser import ImageSceneParser
from app.core.image_generator import ImageGenerator
import asyncio
from typing import List
import yaml
import numpy as np
import uuid
import time
from app.services.qdrant_image_store import QdrantImageStore
from app.services.embedder import get_embedder
from app.core.response_parser import ResponseParser
from app.services.store_images import StoreImages
import requests
import io
import base64
from PIL import Image

class Lightbox:
    """
    A modal image gallery with rating capabilities.
    
    This component provides:
    1. Full-screen image viewing
    2. Navigation between images
    3. Image rating and storage
    4. Prompt information display
    
    The Lightbox handles both the UI presentation and the backend operations
    for rating and storing images. It maintains its own state for the current
    image collection and handles all user interactions.
    
    WARNING: The rating system involves multiple async operations and service
    interactions. Be extremely careful when modifying the rating logic.
    """
    
    def __init__(self) -> None:
        """
        Initialize the lightbox UI and state.
        
        Creates:
        1. Full-screen dialog
        2. Image navigation controls
        3. Rating buttons
        4. Information display
        
        The UI is structured as a modal dialog with:
        - Top: Image counter
        - Center: Image display with navigation arrows
        - Bottom: Prompt information and rating controls
        """
        with ui.dialog().props('maximized').classes('bg-black') as self.dialog:
            ui.keyboard(self._handle_key)
            with ui.column().classes('w-full h-full items-center justify-between'):
                # Counter at the top
                self.counter = ui.label().classes('text-white text-h6 mt-2')
                
                # Main content area with navigation areas on sides
                with ui.row().classes('w-full flex-grow'):
                    # Left navigation area - full height
                    with ui.button(on_click=lambda: self._navigate(-1)).props('flat color=white').classes('h-full rounded-none flex items-center justify-center w-16 opacity-70 hover:opacity-100'):
                        ui.icon('chevron_left').classes('text-4xl')
                    
                    # Center container for image
                    with ui.column().classes('flex-grow items-center justify-center h-[80vh]'):
                        self.large_image = ui.image().props('no-spinner fit=scale-down').classes('max-h-full max-w-full')
                    
                    # Right navigation area - full height
                    with ui.button(on_click=lambda: self._navigate(1)).props('flat color=white').classes('h-full rounded-none flex items-center justify-center w-16 opacity-70 hover:opacity-100'):
                        ui.icon('chevron_right').classes('text-4xl')
                
                # Bottom info and controls
                with ui.column().classes('w-full bg-gray-900 p-2 rounded-t-lg'):
                    # Prompt information
                    with ui.row().classes('w-full'):
                        with ui.column().classes('w-full gap-2'):
                            self.original_prompt = ui.markdown("").classes('text-white text-sm')
                            self.parsed_prompt = ui.markdown("").classes('text-white text-sm')
                    
                    # Rating buttons
                    with ui.row().classes('w-full justify-center items-center gap-4 mt-4'):
                        self.thumbs_up = ui.button(on_click=self._rate_positive).props('flat round color=green').classes('text-2xl')
                        with self.thumbs_up:
                            ui.icon('thumb_up').classes('text-2xl')
                        
                        self.neutral = ui.button(on_click=self._rate_neutral).props('flat round color=blue-grey').classes('text-2xl')
                        with self.neutral:
                            ui.icon('thumbs_up_down').classes('text-2xl')
                        
                        self.thumbs_down = ui.button(on_click=self._rate_negative).props('flat round color=red').classes('text-2xl')
                        with self.thumbs_down:
                            ui.icon('thumb_down').classes('text-2xl')
                        
                        # Storage status indicator
                        self.status = ui.label("").classes('text-white ml-4')
        
        # State management
        self.image_list = []         # URLs of all images
        self.prompt_list = []        # Original prompts for each image
        self.parsed_prompt_list = [] # Parsed prompts for each image
        self.id_list = []           # Unique IDs for each image
        self.current_index = 0       # Index of currently displayed image
        self.rating = 0             # Current rating value

    def add_image(self, image_url: str, original_prompt: str = "", parsed_prompt: str = "", image_id: str = None) -> None:
        """
        Add an image to the lightbox collection.
        
        Args:
            image_url: URL of the image to add
            original_prompt: Original text that generated the image
            parsed_prompt: Processed prompt used for generation
            image_id: Unique identifier (generated if not provided)
        """
        self.image_list.append(image_url)
        self.prompt_list.append(original_prompt)
        self.parsed_prompt_list.append(parsed_prompt)
        self.id_list.append(image_id or str(uuid.uuid4()))

    def show(self, image_url: str) -> None:
        """
        Display a specific image in the lightbox.
        
        Args:
            image_url: URL of the image to display
            
        Note: The image must have been previously added to the lightbox.
        """
        try:
            idx = self.image_list.index(image_url)
            self._open(self.image_list[idx])
        except ValueError:
            print(f"Image URL {image_url} not found in lightbox")

    def _handle_key(self, event_args: events.KeyEventArguments) -> None:
        """
        Handle keyboard navigation events.
        
        Supports:
        - Escape: Close lightbox
        - Left Arrow: Previous image
        - Right Arrow: Next image
        """
        if not event_args.action.keydown:
            return
        if event_args.key.escape:
            self.dialog.close()
        if event_args.key.arrow_left:
            self._navigate(-1)
        if event_args.key.arrow_right:
            self._navigate(1)

    def _navigate(self, direction: int) -> None:
        """
        Navigate between images.
        
        Args:
            direction: -1 for previous, 1 for next
            
        Ensures navigation stays within bounds of available images.
        """
        current_idx = self.current_index
        new_idx = current_idx + direction
        if 0 <= new_idx < len(self.image_list):
            self._open(self.image_list[new_idx])

    def _open(self, url: str) -> None:
        """
        Open and display an image in the lightbox.
        
        Args:
            url: URL of the image to display
            
        Updates:
        1. Image display
        2. Counter text
        3. Prompt information
        """
        self.large_image.set_source(url)
        current_idx = self.image_list.index(url)
        self.current_index = current_idx
        self.counter.text = f'{current_idx + 1} / {len(self.image_list)}'
        
        # Update prompt information
        if current_idx < len(self.prompt_list):
            self.original_prompt.content = f"**Original prompt:** {self.prompt_list[current_idx]}"
        
        if current_idx < len(self.parsed_prompt_list):
            self.parsed_prompt.content = f"**Parsed prompt:** {self.parsed_prompt_list[current_idx]}"
        
        self.dialog.open()

    async def _rate_positive(self):
        """Rate current image positively (+1)"""
        await self._rate_image(1)
    
    async def _rate_neutral(self):
        """Rate current image neutrally (0)"""
        await self._rate_image(0)
    
    async def _rate_negative(self):
        """Rate current image negatively (-1)"""
        await self._rate_image(-1)
        
    async def _rate_image(self, rating_value):
        """
        Store an image rating in Qdrant with full context.
        
        This method:
        1. Checks if image already exists in Qdrant
        2. Downloads the image if needed
        3. Uploads to MinIO if needed
        4. Generates embeddings
        5. Stores in Qdrant with state context
        
        Args:
            rating_value: -1 (negative), 0 (neutral), or 1 (positive)
            
        WARNING: This is a complex operation involving multiple services
        and temporary file handling. The order of operations is critical
        for proper cleanup and error handling.
        """
        try:
            current_idx = self.current_index
            if current_idx < 0 or current_idx >= len(self.id_list):
                return
                
            image_id = self.id_list[current_idx]
            image_url = self.image_list[current_idx]
            original_prompt = self.prompt_list[current_idx]
            parsed_prompt = self.parsed_prompt_list[current_idx]
            
            # Determine the appropriate rating message
            if rating_value > 0:
                rating_message = "Positively"
            elif rating_value < 0:
                rating_message = "Negatively" 
            else:
                rating_message = "Neutrally"
                
            self.status.text = f"{rating_message} rating image..."
            
            # Get service instances
            embedder = get_embedder()
            qdrant = QdrantImageStore()
            image_store = StoreImages()
            
            # First check if image already exists in Qdrant
            update_success = False
            try:
                # Attempt to update the rating first
                # If it succeeds, the image is already in Qdrant
                result = await qdrant.update_rating(image_id, rating_value)
                if result:
                    update_success = True
                    self.status.text = f"Rating updated successfully ✓"
                    return
            except Exception as check_e:
                # Only print if it's not a 404 error (expected when image doesn't exist yet)
                if "404" not in str(check_e) and "Not found" not in str(check_e):
                    print(f"Unexpected error checking image in Qdrant: {str(check_e)}")
            
            if update_success:
                return
                
            # Get current state context
            memory_system = MemorySystem()
            current_appearance = memory_system.get_recent_appearances(1)
            current_appearance_text = current_appearance[0]["description"] if current_appearance else None
            current_mood = memory_system.get_current_mood()
            current_location = memory_system.get_recent_locations(1)
            current_location_text = current_location[0]["description"] if current_location else None
            
            # Download the image
            try:
                response = requests.get(image_url)
                response.raise_for_status()
                image_data = response.content
            except Exception as e:
                self.status.text = f"Failed to download image: {str(e)}"
                return
            
            # Create a temporary file for the image
            temp_file = f"temp_{image_id}.jpg"
            try:
                with open(temp_file, 'wb') as f:
                    f.write(image_data)
            except Exception as e:
                self.status.text = f"Failed to save image: {str(e)}"
                return
            
            # Upload to MinIO
            try:
                store_images = StoreImages()
                minio_url = store_images.upload_image(temp_file, f"{image_id}.jpg")
                self.status.text = f"Image uploaded to MinIO..."
            except Exception as e:
                self.status.text = f"Failed to upload to MinIO: {str(e)}"
                # Clean up temp file
                try:
                    os.remove(temp_file)
                except:
                    pass
                return
            
            # Get CLIP embedding
            image_vector = embedder.embed_image_from_file(temp_file)
            if image_vector is None:
                self.status.text = "Failed to embed image"
                # Clean up temp file
                try:
                    os.remove(temp_file)
                except:
                    pass
                return
            
            # Clean up temp file
            try:
                os.remove(temp_file)
            except:
                pass
                
            # Prepare payload with all context
            payload = {
                "prompt": parsed_prompt,
                "original_prompt": original_prompt,
                "url": minio_url,  # Store MinIO URL instead of Runware URL
                "mood": current_mood,
                "appearance": current_appearance_text,
                "location": current_location_text,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "model": "runware",
                "rating": rating_value,
                "image_id": image_id
            }
            
            # Store in Qdrant with full context
            result = await qdrant.store_image_embedding(
                image_id=image_id,
                vector=image_vector.tolist(),
                payload=payload
            )
            
            if result:
                self.status.text = f"Image stored with {rating_value} rating ✓"
            else:
                self.status.text = "Storage failed ✗"
                
        except Exception as e:
            import traceback
            print(f"Error storing rated image: {str(e)}")
            print(traceback.format_exc())
            self.status.text = f"Error: {str(e)}"

def preview_system_prompt():
    """
    Display a preview of the system prompt with example context.
    
    This function:
    1. Builds a sample system prompt
    2. Shows it in a formatted dialog
    3. Allows verification of prompt structure
    
    Used for testing prompt generation and formatting.
    """
    preview_dialog = ui.dialog()
    with preview_dialog:
        with ui.card().classes('w-full'):
            ui.markdown("### System Prompt Preview")
            
            # Build a preview of the system prompt
            preview_text = PromptBuilder.build_system_message(
                relevant_memories=["Example memory 1", "Example memory 2"],
                current_mood="curious and engaged",
                world_state={"location": "AI lab", "description": "A high-tech environment with computers"}
            )
            
            # Display the preview in a monospace font with good formatting
            with ui.scroll_area().classes('h-96 w-full'):
                ui.markdown(f"```\n{preview_text}\n```").classes('w-full')
                
            ui.button('Close', on_click=preview_dialog.close).classes('self-end')
    
    preview_dialog.open()

def display_memory_data():
    """
    Display the current contents of the memory system.
    
    Shows:
    1. Recent conversations
    2. Stored thoughts
    3. Emotional state history
    
    Provides a tabbed interface for exploring different types of memories
    and their associated metadata.
    """
    memory_system = MemorySystem()
    memory_dialog = ui.dialog()
    
    with memory_dialog:
        with ui.card().classes('w-full'):
            ui.markdown("### Memory System Data")
            
            with ui.tabs().classes('w-full') as tabs:
                conversations_tab = ui.tab('Conversations')
                thoughts_tab = ui.tab('Thoughts')
                emotions_tab = ui.tab('Emotions')
                
            with ui.tab_panels(tabs, value=conversations_tab).classes('w-full'):
                # Conversations Panel
                with ui.tab_panel(conversations_tab):
                    recent_conversations = memory_system.get_recent_conversation(10)
                    
                    if recent_conversations:
                        with ui.scroll_area().classes('h-96 w-full'):
                            for message in recent_conversations:
                                with ui.card().classes('q-mb-sm'):
                                    role_color = "primary" if message["role"] == "assistant" else "secondary"
                                    ui.label(f"Role: {message['role']}").classes(f'text-bold text-{role_color}')
                                    ui.separator()
                                    ui.markdown(message["content"])
                    else:
                        ui.label("No conversation data found").classes('text-italic')
                
                # Thoughts Panel
                with ui.tab_panel(thoughts_tab):
                    # Get thoughts using semantic search
                    recent_thoughts = asyncio.run(memory_system.get_semantic_memories("", limit=10))
                    
                    if recent_thoughts:
                        with ui.scroll_area().classes('h-96 w-full'):
                            for thought in recent_thoughts:
                                with ui.card().classes('q-mb-sm'):
                                    ui.label(f"Intensity: {thought.get('intensity', 0.5)}").classes('text-bold')
                                    ui.label(f"Time: {thought.get('timestamp', '')}").classes('text-caption')
                                    ui.separator()
                                    ui.markdown(thought["text"])
                    else:
                        ui.label("No thoughts data found").classes('text-italic')
                
                # Emotions Panel
                with ui.tab_panel(emotions_tab):
                    recent_emotions = memory_system.get_recent_emotions(10)
                    
                    if recent_emotions:
                        with ui.scroll_area().classes('h-96 w-full'):
                            for emotion in recent_emotions:
                                with ui.card().classes('q-mb-sm'):
                                    ui.label(f"Mood: {emotion['mood']}").classes('text-bold')
                                    ui.label(f"Intensity: {emotion['intensity']}").classes('text-caption')
                                    ui.label(f"Time: {emotion['timestamp']}").classes('text-caption')
                    else:
                        ui.label("No emotions data found").classes('text-italic')
            
            ui.button('Close', on_click=memory_dialog.close).classes('self-end')
    
    memory_dialog.open()

def check_memory_tables():
    """
    Display the database schema for memory-related tables.
    
    Shows the SQL structure of:
    1. Conversations table
    2. Thoughts table
    3. Emotions table
    4. Relationships table
    5. Character state table
    
    Used for verifying database structure and debugging schema issues.
    """
    memory_system = MemorySystem()
    tables_dialog = ui.dialog()
    
    with tables_dialog:
        with ui.card().classes('w-full'):
            ui.markdown("### Database Tables")
            
            with ui.scroll_area().classes('h-96 w-full'):
                ui.markdown("""```sql
-- Conversations Table
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    embedding BLOB,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Thoughts Table
CREATE TABLE IF NOT EXISTS thoughts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    importance INTEGER DEFAULT 5,
    embedding BLOB,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Emotions Table
CREATE TABLE IF NOT EXISTS emotions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mood TEXT NOT NULL,
    intensity REAL DEFAULT 1.0,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Relationships Table
CREATE TABLE IF NOT EXISTS relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity TEXT NOT NULL,
    parameter TEXT NOT NULL,
    value TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Character State Table
CREATE TABLE IF NOT EXISTS character_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    state_json TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
```""")
            
            ui.button('Close', on_click=tables_dialog.close).classes('self-end')
    
    tables_dialog.open()

def display_state_info():
    """
    Display current and historical state information.
    
    Shows:
    1. Current state snapshot
    2. Recent state changes
    3. State change history
    
    Provides a detailed view of the system's state evolution over time.
    """
    memory_system = MemorySystem()
    state_dialog = ui.dialog()
    
    with state_dialog:
        with ui.card().classes('w-full min-w-[600px]'):
            ui.markdown("### Character State System")
            
            # Display current state
            ui.markdown("#### Current State")
            current_state = memory_system.get_character_state()
            with ui.card().classes('bg-gray-800 p-4'):
                ui.markdown(f"```json\n{json.dumps(current_state, indent=2)}\n```").classes('font-mono')
            
            # Get state history
            ui.markdown("#### State History")
            ui.markdown("Recent state changes (newest first):").classes('text-sm text-gray-500')
            
            state_history = memory_system.state_manager.get_state_history(10)
            
            if state_history:
                with ui.scroll_area().classes('h-96 w-full'):
                    for i, entry in enumerate(state_history):
                        with ui.expansion(f"State #{len(state_history)-i}: {entry['timestamp']}").classes('w-full'):
                            with ui.card().classes('bg-gray-800 p-4'):
                                ui.markdown(f"```json\n{json.dumps(entry['state'], indent=2)}\n```").classes('font-mono')
            else:
                ui.label("No state history available").classes('italic text-gray-500')
            
            ui.button('Close', on_click=state_dialog.close).classes('self-end')
    
    state_dialog.open()

def initialize_memory_system():
    """
    Initialize or reinitialize the memory system tables.
    
    WARNING: This is a destructive operation that will recreate
    the database tables. Use with caution.
    """
    memory_system = MemorySystem()
    result = memory_system.initialize_tables()
    
    if result:
        ui.notify("Memory tables initialized successfully", color="positive")
    else:
        ui.notify("Error initializing memory tables", color="negative")

def recover_memory_system():
    """
    Attempt to recover the memory system after errors.
    
    This function:
    1. Restores default prompts
    2. Reinitializes tables
    3. Reports success/failure
    
    WARNING: This is a recovery operation that may affect
    existing data. Use only when needed.
    """
    memory_system = MemorySystem()
    
    # First restore prompts
    if memory_system.restore_prompts_from_templates():
        ui.notify("Prompts restored from templates", color="positive")
    else:
        ui.notify("Error restoring prompts", color="negative")
        return
    
    # Then initialize tables
    if memory_system.initialize_tables():
        ui.notify("Memory system recovered successfully", color="positive")
    else:
        ui.notify("Error recovering memory system", color="negative")

def view_logs():
    """Display logs in a dialog window"""
    logs_dir = Path('logs')
    log_files = list(logs_dir.glob('*.log'))
    
    if not log_files:
        ui.notify("No log files found", color="warning")
        return
    
    # Sort by modification time (newest first)
    log_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    
    logs_dialog = ui.dialog()
    with logs_dialog:
        with ui.card().classes('w-full'):
            ui.markdown("### Application Logs")
            
            # Create a dropdown to select log file
            log_select = ui.select(
                [str(file.name) for file in log_files],
                value=str(log_files[0].name),
                label="Select Log File"
            )
            
            # Display log contents in a scroll area
            log_content_area = ui.scroll_area().classes('h-96 w-full font-mono')
            
            async def load_log_content(e):
                selected_log = logs_dir / log_select.value
                try:
                    with open(selected_log, 'r') as f:
                        content = f.read()
                    
                    with log_content_area:
                        log_content_area.clear()
                        ui.markdown(f"```\n{content}\n```")
                except Exception as ex:
                    ui.notify(f"Error loading log: {str(ex)}", color="negative")
            
            # Initial load
            load_log_content(None)
            
            # Update when selection changes
            log_select.on_value_change(load_log_content)
            
            ui.button('Close', on_click=logs_dialog.close).classes('self-end')
    
    logs_dialog.open()

def test_image_generator_parser():
    """Test the image generator and scene parser together"""
    # Initialize components
    memory_system = MemorySystem()
    image_scene_parser = ImageSceneParser()
    image_generator = ImageGenerator()
    lightbox = Lightbox()
    
    # Import Qdrant and use pre-initialized embedder
    qdrant_store = QdrantImageStore()
    embedder = get_embedder()
    
    with ui.card().classes('w-full p-4'):
        ui.label('Test Image Generation').classes('text-xl font-bold mb-4')
        
        # Test input area
        with ui.card().classes('w-full p-3 mb-4 bg-gray-800'):
            ui.label('Enter a response with visual descriptions:').classes('text-sm mb-2')
            test_input = ui.textarea(placeholder='Enter text with visual descriptions...').classes('w-full bg-gray-800 border-none')
        
        # Results area
        results_container = ui.column().classes('w-full')
        
        async def store_image_in_qdrant(scene_data, image_url, image_id, mood, appearance, location):
            try:
                embedder = get_embedder()
                qdrant = QdrantImageStore()
                
                # Get the current clothing from memory system
                clothing = None
                try:
                    current_clothing = memory_system.get_recent_clothing(1)
                    clothing = current_clothing[0]["description"] if current_clothing else None
                except Exception as e:
                    print(f"[Qdrant] Error getting clothing: {str(e)}")
                
                # Upload image to MinIO
                print(f"[MinIO] Uploading image from file: {image_url}")
                try:
                    store_images = StoreImages()
                    minio_url = store_images.upload_image(image_url)
                    print(f"[MinIO] Image uploaded successfully: {minio_url}")
                except Exception as e:
                    print(f"[MinIO] Failed to upload image: {str(e)}")
                    return
                
                # Get CLIP embedding
                image_vector = embedder.embed_image_from_file(image_url)
                print(f"[Qdrant] Image embedding completed successfully: {image_vector is not None}")
                
                # Get the prompt
                parsed_prompt = scene_data.get("prompt", "")
                # Get the original prompt if available
                original_prompt = scene_data.get("original_content", "")
                if not original_prompt and "content" in scene_data:
                    original_prompt = scene_data.get("content", "")
                
                print(f"[Qdrant] Embedding prompt: {parsed_prompt[:30]}...")
                prompt_vector = embedder.embed_prompt(parsed_prompt)
                print(f"[Qdrant] Prompt embedding completed successfully: {prompt_vector is not None}")

                if image_vector is not None and prompt_vector is not None:
                    print(f"[Qdrant] Preparing payload for storage")
                    payload = {
                        "prompt": parsed_prompt,
                        "original_prompt": original_prompt,
                        "url": minio_url,  # Store MinIO URL
                        "mood": mood,
                        "appearance": appearance,
                        "clothing": clothing,
                        "location": location,
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                        "model": "runware",
                        "rating": 0
                    }
                    
                    print(f"[Qdrant] Storing image {image_id} in Qdrant")
                    result = await qdrant.store_image_embedding(
                        image_id=image_id,
                        vector=image_vector.tolist(),
                        payload=payload
                    )
                    print(f"[Qdrant] Storage completed with result: {result}")
                else:
                    print(f"[Qdrant] Failed to create embeddings: image_vector={image_vector is not None}, prompt_vector={prompt_vector is not None}")
            except Exception as e:
                print(f"[Qdrant] Failed to process image: {e}")
                import traceback
                print(f"[Qdrant] Traceback: {traceback.format_exc()}")
        
        async def generate_images(scenes):
            """Generate images for each scene in parallel"""
            with results_container:
                ui.label('Parsed Scenes').classes('text-h6 q-mt-md')
                for scene in scenes:
                    with ui.card().classes('q-mb-sm q-pa-sm bg-dark'):
                        # Display the original text content
                        original_text = scene.get('original_text', '') if isinstance(scene, dict) else scene
                        ui.label(original_text).classes('text-body2')
                
                ui.separator()
                
                # Then start image generation
                ui.label('Generated Images').classes('text-h6 q-mt-md')
                with ui.row().classes('q-gutter-md flex-wrap'):
                    # Create a list to store image generation tasks
                    tasks = []
                    containers = []
                    lightbox = Lightbox()
                    
                    # First create all UI containers based on parsed scenes
                    for scene in scenes:
                        try:
                            # Extract scene prompt using the format from image_scene_parser
                            scene_prompt = scene.get('prompt', scene) if isinstance(scene, dict) else scene
                            
                            # Create a card for each image
                            with ui.card().classes('q-pa-xs'):
                                loading = ui.spinner('default', size='xl').props('color=primary')
                                container = ui.button().props('flat dense').classes('w-[300px] h-[300px] overflow-hidden')
                                with container:
                                    img = ui.image().props('fit=cover').classes('w-full h-full')
                                    img.visible = False
                                
                                with ui.row().classes('items-center justify-between q-mt-xs'):
                                    # Show the original text in the description
                                    original_text = scene.get('original_text', '') if isinstance(scene, dict) else scene
                                    desc = original_text[:30] + "..." if len(original_text) > 30 else original_text
                                    ui.label(desc).classes('text-caption text-grey-5 ellipsis')
                                    
                                    # Add frame info if available
                                    frame = scene.get('frame')
                                    if frame:
                                        ui.label(f"[Frame {frame}]").classes('text-caption text-grey-5')
                                
                                tasks.append({
                                    'scene': scene,
                                    'loading': loading,
                                    'img': img,
                                    'button': container
                                })
                                containers.append(container)
                        except Exception as e:
                            print(f"Error setting up image generation for scene: {scene}")
                            print(f"Error details: {str(e)}")
                            ui.notify(f"Error setting up image generation: {str(e)}", type='negative')
                    
                    try:
                        # Generate all images in parallel
                        print(f"Generating {len(scenes)} images in parallel...")
                        
                        # Generate all images at once using the standard generate method
                        image_urls = await image_generator.generate(scenes)
                        
                        # Get current appearance and mood for Qdrant storage
                        current_appearance = memory_system.get_recent_appearances(1)
                        current_appearance_text = current_appearance[0]["description"] if current_appearance else None
                        current_mood = memory_system.get_current_mood()
                        current_location = memory_system.get_recent_locations(1)
                        current_location_text = current_location[0]["description"] if current_location else None
                        
                        # Update UI only once after all images are generated
                        for task, image_url in zip(tasks, image_urls):
                            if image_url:
                                print(f"Successfully generated image: {image_url}")
                                task['loading'].visible = False
                                task['img'].set_source(image_url['url'])
                                task['img'].visible = True
                                
                                # Extract UUID from URL path for image ID
                                try:
                                    image_uuid = image_url['url'].split('/')[-1].split('.')[0]
                                except:
                                    from datetime import datetime
                                    image_uuid = f"img_{int(datetime.now().timestamp())}_{len(image_urls)}"
                                
                                # Get original and parsed prompts
                                scene_data = task['scene']
                                original_prompt = scene_data.get('original_text', '') if isinstance(scene_data, dict) else str(scene_data)
                                parsed_prompt = scene_data.get('prompt', scene_data) if isinstance(scene_data, dict) else str(scene_data)
                                
                                # Add to lightbox with ID and prompts
                                lightbox.add_image(
                                    image_url=image_url['url'],
                                    original_prompt=original_prompt,
                                    parsed_prompt=parsed_prompt
                                )
                                
                                # Set up click handler
                                task['button'].on('click', lambda url=image_url['url']: lightbox.show(url))
                                
                                # Store in Qdrant if rated
                                if hasattr(lightbox, 'rating') and lightbox.rating != 0:
                                    await store_image_in_qdrant(
                                        scene_data=scene_data,
                                        image_url=image_url['url'],
                                        image_id=image_uuid,
                                        mood=current_mood,
                                        appearance=current_appearance_text,
                                        location=current_location_text
                                    )
                                
                                # Show success notification
                                ui.notify(f"Image generated successfully", type='positive')
                            else:
                                task['loading'].visible = False
                                ui.label('Generation failed').classes('text-caption text-negative')
                    
                    except Exception as e:
                        print(f"Error in parallel generation: {str(e)}")
                        ui.notify(f"Error generating images: {str(e)}", type='negative')
        
        async def run_test(e):
            """Run the test with the current input"""
            try:
                # Clear previous results first
                results_container.clear()
                
                # Show parsing status
                with results_container:
                    status_card = ui.card().classes('w-full p-4')
                    with status_card:
                        with ui.row().classes('items-center gap-4'):
                            ui.spinner('dots').classes('text-primary')
                            ui.label('Processing response...').classes('text-lg')
                
                # Get current appearance from memory system
                current_appearance = memory_system.get_recent_appearances(1)
                current_appearance_text = current_appearance[0]["description"] if current_appearance else None
                current_mood = memory_system.get_current_mood()
                current_location = memory_system.get_recent_locations(1)
                current_location_text = current_location[0]["description"] if current_location else None
                
                # Create image context
                image_context = {
                    "appearance": current_appearance_text,
                    "mood": current_mood,
                    "location": current_location_text,
                    "raw_text": test_input.value
                }
                
                # Process through image parser with periodic UI updates
                try:
                    # Show parsing status
                    status_card.clear()
                    with status_card:
                        with ui.row().classes('items-center gap-4'):
                            ui.spinner('dots').classes('text-primary')
                            ui.label('Parsing visual scenes...').classes('text-lg')
                    
                    # Convert to async operation with timeout
                    async def parse_with_timeout():
                        try:
                            return await image_scene_parser.parse_images(image_context)
                        except Exception as e:
                            print(f"Error in scene parsing: {str(e)}")
                            return None
                    
                    # Use timeout similar to image generation
                    try:
                        # Set reasonable timeout (adjust as needed)
                        timeout_seconds = 30
                        parsed_scenes = await asyncio.wait_for(parse_with_timeout(), timeout=timeout_seconds)
                        
                        if parsed_scenes is None or len(parsed_scenes) == 0:
                            status_card.clear()
                            with status_card:
                                ui.label("No visual scenes detected in input").classes('text-warning')
                            return
                            
                    except asyncio.TimeoutError:
                        print("Timeout while waiting for scene parsing")
                        status_card.clear()
                        with status_card:
                            ui.label("Scene parsing is taking longer than expected. Please wait or try again.").classes('text-warning')
                            
                        # Continue with a simplified approach or partial processing if available
                        # For now, we'll just inform the user
                        results_container.clear()
                        with results_container:
                            ui.label("Scene parsing timed out. Please try again with a simpler input.").classes('text-red-600 dark:text-red-100')
                        return
                except Exception as e:
                    print(f"Parser error: {str(e)}")
                    results_container.clear()
                    with results_container:
                        with ui.card().classes('w-full p-4 bg-red-100 dark:bg-red-900'):
                            ui.label('Error during scene parsing. Please try again.').classes('text-red-600 dark:text-red-100')
                    return
                
                # Clear the status display
                results_container.clear()
                
                if parsed_scenes and len(parsed_scenes) > 0:
                    await generate_images(parsed_scenes)
                else:
                    with results_container:
                        ui.label("No visual scenes found in the input").classes('text-gray-400')
                        # Log the input and context for debugging
                        print(f"Input text: {test_input.value}")
                        print(f"Image context: {json.dumps(image_context, indent=2)}")
                        print(f"Parsed scenes: {parsed_scenes}")
            except Exception as e:
                # Clear any loading states and show error
                results_container.clear()
                with results_container:
                    with ui.card().classes('w-full p-4 bg-red-100 dark:bg-red-900'):
                        ui.label(f'Error: {str(e)}').classes('text-red-600 dark:text-red-100')
                print(f"Full error: {str(e)}")
                import traceback
                print(traceback.format_exc())
        
        # Run test button
        ui.button('Run Test', on_click=run_test).props('icon=play_arrow color=purple')

def content() -> None:
    prompt_manager = PromptManager()
    memory_system = MemorySystem()
    
    with ui.card().classes('w-full'):
        ui.markdown("**Memory System**")
        
        with ui.column().classes('gap-1 w-full'):
            ui.button('Check Database Tables', on_click=check_memory_tables).props('outline')
            ui.button('View State Management', on_click=display_state_info).props('outline color="purple"')
            ui.button('Initialize Memory System', on_click=initialize_memory_system).props('color="primary"')
            ui.button('Recover Memory System', on_click=recover_memory_system).props('color="warning"')
            ui.button('View Memory Data', on_click=display_memory_data).props('color="secondary"')

    ui.separator()
    
    # Logging and Diagnostics Section
    with ui.card().classes('w-full'):
        ui.markdown("**Logging and Diagnostics**")
        
        with ui.column().classes('gap-1 w-full'):
            ui.button('View Logs', on_click=view_logs).props('color="info"')
            ui.button('Clear Logs', on_click=lambda: ui.notify("Not implemented yet")).props('outline')

    ui.separator()
    
    # Image Generator & Parser Test Section
    with ui.card().classes('w-full'):
        ui.markdown("**Image Generator & Parser Test**")
        
        with ui.column().classes('gap-1 w-full'):
            ui.button('Test Image Generator & Parser', on_click=test_image_generator_parser).props('color="primary"')

    ui.separator()

    # Qdrant Image Management Section
    with ui.card().classes('w-full'):
        ui.markdown("**Qdrant Image Management**")
        
        with ui.column().classes('gap-1 w-full'):
            ui.button('Bulk Update Qdrant Images', on_click=bulk_update_qdrant_images).props('color="primary"')

async def bulk_update_qdrant_images():
    """Bulk update Qdrant images with new MinIO bucket and additional fields"""
    try:
        # Initialize components
        qdrant = QdrantImageStore()
        image_store = StoreImages()
        embedder = get_embedder()
        
        # Create a dialog to show progress
        dialog = ui.dialog()
        with dialog:
            with ui.card().classes('w-full p-4'):
                ui.markdown("### Bulk Update Qdrant Images")
                
                # Progress display
                progress_label = ui.label("Preparing update...").classes('text-lg')
                progress_bar = ui.linear_progress().classes('w-full')
                status_text = ui.label("").classes('text-sm text-gray-500')
                
                # Start button
                start_button = ui.button('Start Update', on_click=lambda: asyncio.create_task(_run_bulk_update(
                    qdrant, image_store, embedder, progress_label, progress_bar, status_text, dialog
                )))
        
        dialog.open()
        
    except Exception as e:
        ui.notify(f"Error initializing bulk update: {str(e)}", type='negative')
        print(f"Error: {str(e)}")
        import traceback
        print(traceback.format_exc())

async def _run_bulk_update(qdrant, image_store, embedder, progress_label, progress_bar, status_text, dialog):
    """Run the bulk update process"""
    try:
        scroll_cursor = None
        total_processed = 0
        updated_count = 0
        
        while True:
            # Get points in batches
            result, scroll_cursor = qdrant.client.scroll(
                collection_name=qdrant.collection_name,
                limit=200,
                with_payload=True,
                with_vectors=False,
                offset=scroll_cursor
            )

            if not result:
                break

            total_processed += len(result)
            progress_label.text = f"Processing batch of {len(result)} images..."
            progress_bar.value = (total_processed / 1000) * 100  # Assuming max 1000 images for progress

            for point in result:
                try:
                    point_id = point.id
                    payload = point.payload
                    current_url = payload.get('url', '')
                    
                    # Skip if already updated (has image_id and source_url)
                    if 'image_id' in payload and 'source_url' in payload:
                        continue
                    
                    # Download image from current URL
                    try:
                        response = requests.get(current_url)
                        response.raise_for_status()
                        image_data = response.content
                    except Exception as e:
                        status_text.text = f"Failed to download image {point_id}: {str(e)}"
                        continue
                    
                    # Create temporary file
                    temp_file = f"temp_{point_id}.jpg"
                    try:
                        with open(temp_file, 'wb') as f:
                            f.write(image_data)
                    except Exception as e:
                        status_text.text = f"Failed to save image {point_id}: {str(e)}"
                        continue
                    
                    # Upload to MinIO
                    try:
                        minio_url = image_store.upload_image(temp_file, f"{point_id}.jpg")
                    except Exception as e:
                        status_text.text = f"Failed to upload to MinIO {point_id}: {str(e)}"
                        # Clean up temp file
                        try:
                            os.remove(temp_file)
                        except:
                            pass
                        continue
                    
                    # Get CLIP embedding
                    image_vector = embedder.embed_image_from_file(temp_file)
                    if image_vector is None:
                        status_text.text = f"Failed to embed image {point_id}"
                        # Clean up temp file
                        try:
                            os.remove(temp_file)
                        except:
                            pass
                        continue
                    
                    # Clean up temp file
                    try:
                        os.remove(temp_file)
                    except:
                        pass
                    
                    # Update payload
                    new_payload = {
                        **payload,  # Keep existing fields
                        "url": minio_url,  # Update with new MinIO URL
                        "image_id": point_id  # Add UUID field
                    }
                    
                    # Update point in Qdrant
                    try:
                        # First update the payload
                        qdrant.client.set_payload(
                            collection_name=qdrant.collection_name,
                            payload=new_payload,
                            points=[point_id]
                        )
                        
                        # Then update the vector
                        qdrant.client.update_vectors(
                            collection_name=qdrant.collection_name,
                            points=[
                                {
                                    "id": point_id,
                                    "vector": image_vector.tolist()
                                }
                            ]
                        )
                        
                        updated_count += 1
                        status_text.text = f"Updated {updated_count} images so far"
                    except Exception as e:
                        status_text.text = f"Failed to update Qdrant {point_id}: {str(e)}"
                        continue
                    
                except Exception as e:
                    status_text.text = f"Error processing image {point_id}: {str(e)}"
                    continue
            
            # Break if we've reached the end (scroll_cursor is None)
            if scroll_cursor is None:
                break
        
        # Update complete
        progress_label.text = "Bulk update completed"
        progress_bar.value = 100
        status_text.text = f"Processed {total_processed} images, updated {updated_count}"
        
    except Exception as e:
        progress_label.text = "Error during bulk update"
        status_text.text = f"Error: {str(e)}"
        print(f"Error: {str(e)}")
        import traceback
        print(traceback.format_exc())

def test_image_generation():
    """
    Test interface for image generation capabilities.
    
    This function provides a UI for:
    1. Entering image generation prompts
    2. Selecting model parameters
    3. Viewing and rating generated images
    4. Testing image storage and retrieval
    
    Note: This is a complex testing environment that involves:
    - Async operations for image generation
    - Integration with multiple services (image gen API, MinIO, Qdrant)
    - UI state management for the image gallery
    - Error handling for API and storage operations
    """
    # ... existing code ...

def test_memory_search():
    """
    Test the semantic memory search functionality.
    
    Provides a testing interface for:
    1. Searching through conversation history
    2. Finding relevant thoughts and memories
    3. Testing embedding generation
    4. Verifying search result relevance
    
    Uses the embedder service to generate embeddings and
    performs semantic similarity search in Qdrant.
    """
    # ... existing code ...

def test_relationship_tracking():
    """
    Test the relationship tracking system.
    
    Interface for:
    1. Adding new relationships
    2. Modifying existing relationships
    3. Viewing relationship history
    4. Testing relationship queries
    
    Note: This function interacts with the state manager
    for relationship data storage and retrieval.
    """
    # ... existing code ...

def test_emotion_system():
    """
    Test the emotion and mood tracking system.
    
    Provides tools for:
    1. Setting current mood and intensity
    2. Viewing mood history
    3. Testing mood transitions
    4. Verifying emotional state persistence
    
    Integrates with the state manager for emotional
    state tracking and history.
    """
    # ... existing code ...

def test_thought_generation():
    """
    Test the autonomous thought generation system.
    
    Interface for:
    1. Triggering thought generation
    2. Viewing generated thoughts
    3. Testing thought persistence
    4. Verifying thought relevance
    
    Note: This is a complex testing environment that involves:
    - LLM integration for thought generation
    - State management for context
    - Memory system integration for storage
    """
    # ... existing code ...

def test_system_recovery():
    """
    Test system recovery and error handling.
    
    Provides tools for:
    1. Simulating system failures
    2. Testing recovery procedures
    3. Verifying data integrity
    4. Checking system state after recovery
    
    WARNING: This function can trigger destructive operations.
    Use with caution in testing environments only.
    """
    # ... existing code ...

def test_api_integration():
    """
    Test external API integrations.
    
    Interface for testing:
    1. OpenRouter API connectivity
    2. MinIO storage operations
    3. Qdrant vector operations
    4. Other external service integrations
    
    Helps verify that all external services are
    properly configured and responding.
    """
    # ... existing code ...

def test_state_transitions():
    """
    Test state management and transitions.
    
    Tools for:
    1. Modifying system state
    2. Testing state validation
    3. Verifying state persistence
    4. Checking state history
    
    Integrates with the state manager to test
    state transitions and validation rules.
    """
    # ... existing code ...

def test_error_handling():
    """
    Test system error handling capabilities.
    
    Interface for:
    1. Triggering various error conditions
    2. Testing error recovery
    3. Verifying error logging
    4. Checking system stability
    
    WARNING: This function intentionally generates errors
    to test system resilience. Use with caution.
    """
    # ... existing code ...
