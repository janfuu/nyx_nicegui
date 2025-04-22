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
import uuid  # Add this import
from app.services.qdrant_client import QdrantImageStore
from app.main import get_embedder

class Lightbox:
    """A thumbnail gallery where each image can be clicked to enlarge."""
    def __init__(self) -> None:
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
        
        self.image_list = []
        self.prompt_list = []
        self.parsed_prompt_list = []
        self.id_list = []
        self.current_index = 0

    def add_image(self, thumb_url: str, orig_url: str, image_id: str, original_prompt: str, parsed_prompt: str) -> ui.image:
        """Place a thumbnail image in the UI and make it clickable to enlarge."""
        self.image_list.append(orig_url)
        self.prompt_list.append(original_prompt)
        self.parsed_prompt_list.append(parsed_prompt)
        self.id_list.append(image_id)
        
        with ui.button(on_click=lambda: self._open(orig_url)).props('flat dense square'):
            return ui.image(thumb_url)

    def _handle_key(self, event_args: events.KeyEventArguments) -> None:
        if not event_args.action.keydown:
            return
        if event_args.key.escape:
            self.dialog.close()
        if event_args.key.arrow_left:
            self._navigate(-1)
        if event_args.key.arrow_right:
            self._navigate(1)

    def _navigate(self, direction: int) -> None:
        """Navigate through images. direction should be -1 for previous or 1 for next."""
        current_idx = self.current_index
        new_idx = current_idx + direction
        if 0 <= new_idx < len(self.image_list):
            self._open(self.image_list[new_idx])

    def _open(self, url: str) -> None:
        self.large_image.set_source(url)
        current_idx = self.image_list.index(url)
        self.current_index = current_idx
        self.counter.text = f'{current_idx + 1} / {len(self.image_list)}'
        
        # Update prompt information
        if current_idx < len(self.prompt_list):
            self.original_prompt.content = f"**Original prompt:** {self.prompt_list[current_idx]}"
        
        if current_idx < len(self.parsed_prompt_list):
            self.parsed_prompt.content = f"**Parsed prompt:** {self.parsed_prompt_list[current_idx]}"
        
        # Reset status
        self.status.text = ""
        
        self.dialog.open()
    
    async def _rate_positive(self):
        """Rate the current image positively and store it in Qdrant"""
        await self._rate_image(1)
    
    async def _rate_neutral(self):
        """Rate the current image neutrally and store in Qdrant with neutral rating"""
        await self._rate_image(0)
    
    async def _rate_negative(self):
        """Rate the current image negatively and store in Qdrant with negative rating"""
        await self._rate_image(-1)
        
    async def _rate_image(self, rating_value):
        """Store image in Qdrant with specified rating"""
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
            
            # Get embedder and Qdrant client
            from app.main import get_embedder
            from app.services.qdrant_client import QdrantImageStore
            
            embedder = get_embedder()
            qdrant = QdrantImageStore()
            
            # First check if the image already exists in Qdrant
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
                
            # Get current appearance and mood
            from app.core.memory_system import MemorySystem
            memory_system = MemorySystem()
            current_appearance = memory_system.get_recent_appearances(1)
            current_appearance_text = current_appearance[0]["description"] if current_appearance else None
            current_mood = memory_system.get_current_mood()
            current_location = memory_system.get_recent_locations(1)
            current_location_text = current_location[0]["description"] if current_location else None
            
            # Embed the image
            image_vector, thumbnail_b64 = embedder.embed_image_from_url(image_url)
            if image_vector is None:
                self.status.text = "Failed to embed image"
                return
                
            # Prepare payload
            import time
            payload = {
                "prompt": parsed_prompt,
                "original_prompt": original_prompt,  # Store both prompts
                "url": image_url,
                "thumbnail_b64": thumbnail_b64,
                "mood": current_mood,
                "appearance": current_appearance_text,
                "location": current_location_text,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "model": "runware",
                "rating": rating_value
            }
            
            # Store in Qdrant
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
    """Generate and display a preview of the combined system prompt"""
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
    """Display memory data in a dialog window"""
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
                    recent_thoughts = memory_system.get_recent_thoughts(10)
                    
                    if recent_thoughts:
                        with ui.scroll_area().classes('h-96 w-full'):
                            for thought in recent_thoughts:
                                with ui.card().classes('q-mb-sm'):
                                    ui.label(f"Importance: {thought['importance']}").classes('text-bold')
                                    ui.label(f"Time: {thought['timestamp']}").classes('text-caption')
                                    ui.separator()
                                    ui.markdown(thought["content"])
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
    """Check if memory tables exist and show their structure"""
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

-- Appearance Table
CREATE TABLE IF NOT EXISTS appearance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Locations Table
CREATE TABLE IF NOT EXISTS locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
```""")
            
            ui.button('Close', on_click=tables_dialog.close).classes('self-end')
    
    tables_dialog.open()

def initialize_memory_system():
    """Initialize the memory system tables and show result"""
    memory_system = MemorySystem()
    result = memory_system.initialize_tables()
    
    if result:
        ui.notify("Memory tables initialized successfully", color="positive")
    else:
        ui.notify("Error initializing memory tables", color="negative")

def recover_memory_system():
    """Recover the memory system by restoring prompts and reinitializing tables"""
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
        
        async def generate_images(scenes):
            """Generate images for each scene in parallel"""
            with results_container:
                ui.label('Parsed Scenes').classes('text-h6 q-mt-md')
                for scene in scenes:
                    with ui.card().classes('q-mb-sm q-pa-sm bg-dark'):
                        # Display the scene content, handling different formats
                        scene_prompt = scene.get('prompt', scene) if isinstance(scene, dict) else scene
                        ui.label(scene_prompt).classes('text-body2')
                
                ui.separator()
                
                # Then start image generation
                ui.label('Generated Images').classes('text-h6 q-mt-md')
                with ui.row().classes('q-gutter-md flex-wrap'):
                    # Create a list to store image generation tasks
                    tasks = []
                    containers = []
                    lightbox = Lightbox()
                    
                    # First create all UI containers
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
                                    desc = scene_prompt[:30] + "..." if len(scene_prompt) > 30 else scene_prompt
                                    ui.label(desc).classes('text-caption text-grey-5 ellipsis')
                                
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
                        
                        # Get the image tags from the original context
                        # This needs to be retrieved from run_test's image_tags
                        original_image_tags = getattr(run_test, 'image_tags', [])
                        
                        # Update UI only once after all images are generated
                        for i, (task, image_url) in enumerate(zip(tasks, image_urls)):
                            if image_url:
                                print(f"Successfully generated image {i+1}: {image_url}")
                                task['loading'].visible = False
                                task['img'].set_source(image_url)
                                task['img'].visible = True
                                
                                # Extract UUID from URL path for image ID
                                try:
                                    image_uuid = image_url.split('/')[-1].split('.')[0]
                                except:
                                    from datetime import datetime
                                    image_uuid = f"img_{int(datetime.now().timestamp())}_{i}"
                                
                                # Get original and parsed prompts
                                scene_data = task['scene']
                                original_prompt = ""
                                if i < len(original_image_tags):
                                    original_prompt = original_image_tags[i]["content"]
                                
                                parsed_prompt = scene_data.get('prompt', scene_data) if isinstance(scene_data, dict) else str(scene_data)
                                
                                # Add to lightbox with ID and prompts
                                lightbox.add_image(
                                    thumb_url=image_url,
                                    orig_url=image_url,
                                    image_id=image_uuid,
                                    original_prompt=original_prompt,
                                    parsed_prompt=parsed_prompt
                                )
                                
                                # Set up click handler
                                task['button'].on('click', lambda url=image_url: lightbox._open(url))
                                
                                # Show success notification
                                ui.notify(f"Image {i+1} generated successfully", type='positive')
                            else:
                                task['loading'].visible = False
                                ui.label('Generation failed').classes('text-caption text-negative')
                    
                    except Exception as e:
                        print(f"Error in parallel generation: {str(e)}")
                        ui.notify(f"Error generating images: {str(e)}", type='negative')
        
        async def run_and_notify(i, scene_prompt, image_url, image_uuid, current_mood, current_appearance_text, current_location_text):
            # Simple notification without attempting Qdrant storage
            ui.notify(f"Image {i+1} generated successfully", type='positive')
            print(f"Generated image {i+1}: {image_url}")
            print(f"Note: Qdrant storage is handled by the main chat pipeline, not the test UI")
        
        async def store_image_in_qdrant(scene_prompt, image_url, image_id, mood, appearance, location):
            """
            This function is intentionally disabled in the test UI.
            Qdrant storage is properly handled by ChatPipeline._process_image_for_qdrant during normal operation.
            """
            print(f"[TEST UI] Image would be stored in Qdrant during normal operation: {image_id}")
            print(f"[TEST UI] Image storage is handled by ChatPipeline._process_image_for_qdrant")
            # Return immediately without attempting storage
            return
        
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
                            ui.label('Processing visual scenes...').classes('text-lg')
                
                # Get current appearance from memory system
                current_appearance = memory_system.get_recent_appearances(1)
                current_appearance_text = current_appearance[0]["description"] if current_appearance else None
                current_mood = memory_system.get_current_mood()
                current_location = memory_system.get_recent_locations(1)
                current_location_text = current_location[0]["description"] if current_location else None
                
                # Extract image tags from input
                import re
                image_pattern = r'<image>(.*?)</image>'
                image_tags = re.findall(image_pattern, test_input.value, re.DOTALL)
                
                if not image_tags:
                    results_container.clear()
                    with results_container:
                        ui.label("No <image> tags found in the input").classes('text-gray-400')
                    return
                
                # Format image contents with context and sequence
                image_context = {
                    "appearance": current_appearance_text,
                    "mood": current_mood,
                    "location": current_location_text,
                    "images": [{"content": tag.strip(), "sequence": i+1} for i, tag in enumerate(image_tags)]
                }
                
                # Store image_tags as an attribute to access in generate_images
                run_test.image_tags = image_context["images"]
                
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
                            return await image_scene_parser.parse_images(
                                json.dumps(image_context),
                                current_appearance=current_appearance_text
                            )
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
            ui.button('Initialize Memory System', on_click=initialize_memory_system).props('color="primary"')
            ui.button('Recover Memory System', on_click=recover_memory_system).props('color="warning"')
            ui.button('View Memory Data', on_click=display_memory_data).props('color="secondary"')

    ui.separator()
    
    # Prompt File Management Section
    with ui.card().classes('w-full'):
        ui.markdown("**Prompt File Management**")
        
        with ui.column().classes('gap-1 w-full'):
            # File selection dropdown
            prompt_files = [f for f in Path('prompts').glob('*.yaml') if f.is_file()]
            if not prompt_files:
                ui.notify("No prompt files found in the prompts directory", color="warning")
                return
                
            file_select = ui.select(
                [str(file.name) for file in prompt_files],
                value=str(prompt_files[0].name) if prompt_files else None,
                label="Select Prompt File"
            ).classes('w-full')
            
            # Preview area
            preview_area = ui.scroll_area().classes('h-96 w-full font-mono')
            
            # Load and preview button
            def load_and_preview():
                if not file_select.value:
                    ui.notify("No file selected", color="negative")
                    return
                
                try:
                    file_path = Path('prompts') / file_select.value
                    if not file_path.exists():
                        ui.notify(f"File {file_select.value} not found", color="negative")
                        return
                        
                    with open(file_path, 'r') as f:
                        content = f.read()
                    
                    with preview_area:
                        preview_area.clear()
                        ui.markdown(f"```yaml\n{content}\n```")
                    
                    ui.notify(f"Loaded {file_select.value}", color="positive")
                except Exception as e:
                    ui.notify(f"Error loading file: {str(e)}", color="negative")
            
            ui.button('View File', on_click=load_and_preview).props('color="primary"')

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
