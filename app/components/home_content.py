from nicegui import ui, app, events, background_tasks
from ..services.chat_pipeline import ChatPipeline
import time
import asyncio
from ..core.memory_system import MemorySystem
import httpx
import json
from typing import List
import re
from .lightbox import Lightbox
import uuid

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

    def add_image(self, thumb_url: str, orig_url: str, image_id: str = None, original_prompt: str = "", parsed_prompt: str = "") -> ui.image:
        """Place a thumbnail image in the UI and make it clickable to enlarge."""
        self.image_list.append(orig_url)
        
        # Store prompts and ID if provided
        self.prompt_list.append(original_prompt)
        self.parsed_prompt_list.append(parsed_prompt)
        
        # Generate an ID if not provided
        if image_id is None:
            import uuid
            image_id = str(uuid.uuid4())
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
            print(f"Navigating from image {current_idx+1} to {new_idx+1} of {len(self.image_list)}")
            self._open(self.image_list[new_idx])
        else:
            print(f"Cannot navigate: current={current_idx+1}, requested={new_idx+1}, total={len(self.image_list)}")

    def _open(self, url: str) -> None:
        try:
            print(f"Opening image URL: {url}")
            self.large_image.set_source(url)
            current_idx = self.image_list.index(url)
            self.current_index = current_idx
            self.counter.text = f'{current_idx + 1} / {len(self.image_list)}'
            
            # Update prompt information if available
            if current_idx < len(self.prompt_list) and self.prompt_list[current_idx]:
                self.original_prompt.content = f"**Original prompt:** {self.prompt_list[current_idx]}"
            else:
                self.original_prompt.content = ""
            
            if current_idx < len(self.parsed_prompt_list) and self.parsed_prompt_list[current_idx]:
                self.parsed_prompt.content = f"**Parsed prompt:** {self.parsed_prompt_list[current_idx]}"
            else:
                self.parsed_prompt.content = ""
            
            # Reset status
            self.status.text = ""
            
            self.dialog.open()
        except Exception as e:
            print(f"Error in lightbox._open: {str(e)}")
            import traceback
            print(traceback.format_exc())
    
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

# Initialize the chat pipeline
chat_pipeline = ChatPipeline()

# Helper function to clean response text by removing image tags
def clean_response_text(text):
    """Process the main text with [[tag]] markers for UI display"""
    # Define tag markers and their UI representations
    tag_markers = {
        '[[mood]]': '<span class="mood-marker">😊</span>',
        '[[thought]]': '<span class="thought-marker">💭</span>',
        '[[appearance]]': '<span class="appearance-marker">👤</span>',
        '[[clothing]]': '<span class="clothing-marker">👕</span>',
        '[[image]]': '<span class="image-marker">🖼️</span>',
        '[[fantasy]]': '<span class="fantasy-marker">✨</span>',
        '[[desire]]': '<span class="desire-marker">❤️</span>',
        '[[memory]]': '<span class="memory-marker">📚</span>',
        '[[secret]]': '<span class="secret-marker">🔒</span>'
    }
    
    # Replace all tag markers with their UI representations
    for marker, replacement in tag_markers.items():
        text = text.replace(marker, replacement)
    
    return text

def display_message(chat_box, response, memory_system):
    """Display a message in the chat box with proper formatting and tag handling"""
    # Create a message container for text and related images
    with ui.card().classes('self-start bg-gray-700 p-3 rounded-lg mb-3 max-w-3/4 border-l-4 border-blue-500'):
        # Clean response text by removing image tags before displaying
        cleaned_text = clean_response_text(response['text'])
        ui.markdown(cleaned_text).classes('text-white')
        
        # Add indicator for hidden content if present
        if has_hidden_content(response['text']):
            with ui.row().classes('justify-end items-center mt-1'):
                ui.icon('lock', color='grey').classes('text-xs')
        
        # Display generated images if present
        if response.get("images") and len(response["images"]) > 0:
            ui.separator().classes('my-2')
            with ui.row().classes('q-gutter-sm flex-wrap justify-center'):
                # Create a list to store image generation tasks
                tasks = []
                containers = []
                lightbox = Lightbox()  # Initialize lightbox here
                
                # First create all UI containers
                for image_data in response["images"]:
                    if isinstance(image_data, dict) and "url" in image_data and "description" in image_data:
                        try:
                            # Create a card for each image - make it much smaller
                            with ui.card().classes('q-pa-xs'):
                                loading = ui.spinner('default', size='md').props('color=primary')
                                container = ui.button().props('flat dense').classes('w-[120px] h-[120px] overflow-hidden')
                                with container:
                                    img = ui.image().props('fit=cover').classes('w-full h-full')
                                    img.visible = False
                                
                                with ui.row().classes('items-center justify-between q-mt-xs'):
                                    desc = image_data["description"][:30] + "..." if len(image_data["description"]) > 30 else image_data["description"]
                                    ui.label(desc).classes('text-caption text-grey-5 ellipsis')
                                    
                                    # Add orientation and frame info if available
                                    orientation = image_data.get("orientation", "")
                                    frame = image_data.get("frame", None)
                                    if orientation or frame:
                                        frame_text = f"[Frame {frame} | {orientation}]" if frame else f"[{orientation}]"
                                        ui.label(frame_text).classes('text-caption text-grey-5')
                                
                                tasks.append({
                                    'scene': image_data["description"],
                                    'loading': loading,
                                    'img': img,
                                    'button': container
                                })
                                containers.append(container)
                        except Exception as e:
                            print(f"Error setting up image display: {str(e)}")
                            ui.notify(f"Error displaying image: {str(e)}", type='negative')
                
                # Update UI for all images
                for i, task in enumerate(tasks):
                    try:
                        # Get the right image data for this task
                        current_image = response["images"][i]
                        
                        task['loading'].visible = False
                        task['img'].set_source(current_image["url"])
                        task['img'].visible = True
                        
                        # Generate a guaranteed unique ID for each image
                        import uuid
                        image_uuid = str(uuid.uuid4())
                        
                        # Get the original and parsed prompts from the image data
                        scene_data = current_image.get("scene_data", {})
                        original_prompt = scene_data.get("original_text", current_image.get("description", ""))
                        parsed_prompt = scene_data.get("prompt", current_image.get("description", ""))
                            
                        # Add to lightbox with prompts
                        lightbox.add_image(
                            thumb_url=current_image["url"],
                            orig_url=current_image["url"],
                            image_id=image_uuid,
                            original_prompt=original_prompt,
                            parsed_prompt=parsed_prompt
                        )
                        
                        # Set up click handler - update to use the lightbox
                        task['button'].on('click', lambda url=current_image["url"]: lightbox._open(url))
                    except Exception as e:
                        print(f"Error updating image display: {str(e)}")
                        task['loading'].visible = False
                        ui.label('Display failed').classes('text-caption text-negative')

# Function to check if text contains hidden content tags
def has_hidden_content(text):
    """Check if the text contains any secret content tags"""
    return '[[secret]]' in text

def content() -> None:
    # Initialize memory system
    memory_system = MemorySystem()
    lightbox = Lightbox()  # Initialize lightbox
    
    # Get initial state from database
    initial_mood = memory_system.get_current_mood()
    initial_thoughts = memory_system.get_recent_thoughts(1)
    initial_appearances = memory_system.get_recent_appearances(1)
    initial_clothing = memory_system.get_recent_clothing(1)
    
    # Test mode flag
    test_mode = False
    
    # Reference to the portrait image element for updating
    portrait_ref = None
    
    # Track if we have a message processing task running
    is_processing = False
    
    # Heartbeat mechanism to keep connection alive during long operations
    def setup_heartbeat():
        # This function sends small UI updates every few seconds
        # to keep the websocket connection alive during long operations
        async def heartbeat_task():
            heartbeat_counter = 0
            while is_processing:
                # Just ping with a UI update to keep connection alive
                # No need to update text since we have visible spinners now
                ui.update()
                heartbeat_counter += 1
                await asyncio.sleep(3)  # Send a heartbeat every 3 seconds
        
        return background_tasks.create(heartbeat_task())
    
    async def set_as_portrait(image_url):
        """Copy the image to the portrait location"""
        try:
            # Download the image
            async with httpx.AsyncClient() as client:
                response = await client.get(image_url)
                response.raise_for_status()
                
                # Save to assets directory
                portrait_path = 'app/assets/images/portrait.jpg'
                with open(portrait_path, 'wb') as f:
                    f.write(response.content)
            
            # Update the portrait in the UI
            if portrait_ref:
                portrait_ref.set_source(portrait_path)
            ui.notify('Portrait updated successfully!', color='positive')
        except Exception as e:
            ui.notify(f'Failed to update portrait: {str(e)}', color='negative')
    
    with ui.row().classes('w-full gap-4 flex-nowrap'):
        # Left Card
        with ui.card().classes('flex-1 max-w-[512px]'):
            with ui.column().classes('gap-4 w-full'):
                # Store reference to portrait image
                portrait_path = 'app/assets/images/portrait.jpg'
                portrait_ref = ui.image(portrait_path).classes('w-full max-w-[512px] max-h-[512px] rounded-xl')
                
                # Character's current mood display
                ui.label('MOOD').classes('text-blue-500 text-sm')
                with ui.card().classes('bg-[#1a1a1a] p-3 rounded w-full'):
                    mood_display = ui.markdown(initial_mood).classes('text-sm')

                # Character's current appearance display
                ui.label('APPEARANCE').classes('text-purple-500 text-sm')
                with ui.card().classes('bg-[#1a1a1a] p-3 rounded w-full'):
                    initial_appearance = initial_appearances[0]["description"] if initial_appearances else "A young woman with cybernetic enhancements, circuits glowing faintly beneath her skin..."
                    appearance_display = ui.markdown(initial_appearance).classes('text-sm')

                # Character's current clothing display
                ui.label('CLOTHING').classes('text-pink-500 text-sm')
                with ui.card().classes('bg-[#1a1a1a] p-3 rounded w-full'):
                    initial_clothing_text = initial_clothing[0]["description"] if initial_clothing else "Simple, form-fitting black bodysuit with glowing blue circuit patterns..."
                    clothing_display = ui.markdown(initial_clothing_text).classes('text-sm')

                # Character's thoughts display
                ui.label('THOUGHTS').classes('text-gray-500 text-sm')
                with ui.card().classes('bg-[#1a1a1a] p-3 rounded w-full'):
                    initial_thought = initial_thoughts[0]["content"] if initial_thoughts else "It's... unusual to be addressed so familiarly..."
                    thoughts_display = ui.markdown(initial_thought).classes('text-sm')

        # Center Card
        with ui.card().classes('flex-2 w-[800px]'):
            with ui.column().classes('h-full w-full gap-4'):
                # Add test mode toggle at the top of the chat
                with ui.row().classes('w-full justify-between items-center mb-2'):
                    ui.label('Chat Interface').classes('text-lg font-bold')
                    
                    with ui.row().classes('items-center gap-2'):
                        test_toggle = ui.switch('Test Mode', on_change=lambda e: toggle_test_mode(e.value))
                        test_toggle.props('color=purple dense')
                        test_help = ui.button(icon='help_outline').props('flat round dense').classes('text-xs')
                        
                        def show_test_help():
                            ui.notify(
                                'Test Mode echoes input as response without calling the LLM. '
                                'Use <image>description</image> tags to test image generation.',
                                type='info',
                                close_button='OK',
                                timeout=10000
                            )
                        
                        test_help.on_click(show_test_help)
                
                # Chat display area - use a simple scrollable container
                chat_container = ui.scroll_area().classes('h-[560px] w-full')  # Slightly reduced height to accommodate test mode toggle
                with chat_container:
                    chat_box = ui.column().classes('p-6 bg-[#1a1a1a] rounded w-full')
                
                # Function to display image details
                def show_image_details(image_data):
                    lightbox._open(image_data["url"])
                
                # Message input and send button
                with ui.row().classes('gap-4 mt-auto w-full'):
                    msg_input = ui.textarea(placeholder='Type a message...')\
                        .classes('flex-1 bg-[#1f1f1f] text-white')\
                        .props('auto-grow')
                    
                    def send_message():
                        """Handle the send button click or Enter key"""
                        nonlocal is_processing
                        
                        user_message = msg_input.value
                        if not user_message.strip():
                            return
                        
                        # Prevent multiple submissions while processing
                        if is_processing:
                            ui.notify('Still processing your previous message, please wait...', color='warning')
                            return
                            
                        # Set processing flag
                        is_processing = True
                        
                        # Clear input immediately
                        current_message = user_message
                        msg_input.value = ""
                        
                        # Disable the send button during processing
                        send_button.props('disabled')
                        
                        # Display user message immediately
                        with chat_box:
                            user_msg = ui.label(f"You: {current_message}").classes('self-end bg-blue-800 p-2 rounded-lg mb-2 max-w-3/4')
                            # Add visible spinner row directly in the chat
                            spinner_row = ui.row().classes('w-full justify-center my-4')
                            with spinner_row:
                                ui.spinner('dots', size='lg', color='primary')
                                phase_label = ui.label('Thinking...').classes('text-gray-400 ml-2')
                        
                        # Ensure UI updates before continuing
                        ui.update()

                        async def process_message():
                            nonlocal is_processing
                            # Start a heartbeat to keep connection alive
                            heartbeat_task = setup_heartbeat()
                            
                            # Initialize update flags
                            has_thoughts_update = False
                            has_mood_update = False
                            has_appearance_update = False
                            has_clothing_update = False
                            has_location_update = False
                            
                            try:
                                if test_mode:
                                    # In test mode, create a mock response that echoes the input
                                    # Extract all types of tags - handle both formats
                                    image_tags = re.findall(r'(?:<image>|\[\[image\]\])(.*?)(?:</image>|\[\[/image\]\])', current_message, re.DOTALL)
                                    thought_tags = re.findall(r'(?:<thought>|\[\[thought\]\])(.*?)(?:</thought>|\[\[/thought\]\])', current_message, re.DOTALL)
                                    mood_tags = re.findall(r'(?:<mood>|\[\[mood\]\])(.*?)(?:</mood>|\[\[/mood\]\])', current_message, re.DOTALL)
                                    appearance_tags = re.findall(r'(?:<appearance>|\[\[appearance\]\])(.*?)(?:</appearance>|\[\[/appearance\]\])', current_message, re.DOTALL)
                                    location_tags = re.findall(r'(?:<location>|\[\[location\]\])(.*?)(?:</location>|\[\[/location\]\])', current_message, re.DOTALL)
                                    clothing_tags = re.findall(r'(?:<clothing>|\[\[clothing\]\])(.*?)(?:</clothing>|\[\[/clothing\]\])', current_message, re.DOTALL)
                                    
                                    # Also look for secret tags that will be hidden but indicated with a lock icon
                                    secret_tags = re.findall(r'(?:<secret>|\[\[secret\]\])(.*?)(?:</secret>|\[\[/secret\]\])', current_message, re.DOTALL)
                                    desire_tags = re.findall(r'(?:<desire>|\[\[desire\]\])(.*?)(?:</desire>|\[\[/desire\]\])', current_message, re.DOTALL)
                                    internal_tags = re.findall(r'(?:<internal>|\[\[internal\]\])(.*?)(?:</internal>|\[\[/internal\]\])', current_message, re.DOTALL)
                                    
                                    # Create a mock response with only the tags that were included
                                    mock_response = {
                                        'text': f"Echo: {current_message}",
                                        'images': []
                                    }
                                    
                                    # Only include thoughts if thought tags were found
                                    if thought_tags:
                                        mock_response['thoughts'] = thought_tags
                                    
                                    # Only include mood if mood tags were found
                                    if mood_tags:
                                        mock_response['mood'] = mood_tags[0]  # Only use the first mood tag
                                    
                                    # Only include appearance if appearance tags were found
                                    if appearance_tags:
                                        mock_response['appearance'] = appearance_tags
                                    
                                    # Only include clothing if clothing tags were found
                                    if clothing_tags:
                                        mock_response['clothing'] = clothing_tags
                                    
                                    # Only include location if location tags were found
                                    if location_tags:
                                        mock_response['location'] = location_tags[0]  # Only use the first location tag
                                    
                                    # If image tags were found, process them through the actual image generation pipeline
                                    if image_tags:
                                        # Get current state for image generation
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
                                            "images": [{"content": content, "sequence": i+1} for i, content in enumerate(image_tags)]
                                        }
                                        
                                        # Parse scenes using the actual parser
                                        parsed_scenes = await chat_pipeline.image_scene_parser.parse_images(
                                            json.dumps(image_context),
                                            current_appearance=current_appearance_text
                                        )
                                        
                                        if parsed_scenes:
                                            # Generate images using the actual generator
                                            image_urls = await chat_pipeline.image_generator.generate(parsed_scenes)
                                            
                                            # Process results
                                            for i, image_url in enumerate(image_urls):
                                                if image_url:
                                                    # Get the sequence number from the frame field if present, otherwise use index + 1
                                                    sequence = parsed_scenes[i].get("frame", i + 1)
                                                    try:
                                                        image_uuid = image_url.split('/')[-1].split('.')[0]
                                                    except:
                                                        image_uuid = f"img_{int(time.time())}_{i}"
                                                    
                                                    # Get the original content from the corresponding input image
                                                    original_prompt = ""
                                                    if i < len(image_tags):
                                                        original_prompt = image_tags[i]
                                                    
                                                    mock_response['images'].append({
                                                        "url": image_url,
                                                        "description": parsed_scenes[i].get("content", parsed_scenes[i].get("prompt", "Generated image")),
                                                        "id": image_uuid,
                                                        "sequence": sequence,
                                                        "original_prompt": original_prompt,
                                                        "parsed_prompt": parsed_scenes[i].get("prompt", ""),
                                                        "scene_data": parsed_scenes[i]  # Include the full scene data
                                                    })
                                    
                                    response = mock_response
                                else:
                                    # Update phase to "Generating response..."
                                    phase_label.text = "Generating response..."
                                    ui.update()
                                    
                                    # Get LLM response with timeout in normal mode
                                    response = await asyncio.wait_for(
                                        chat_pipeline.process_message(current_message),
                                        timeout=120  # Increased timeout to 120 seconds
                                    )
                                    
                                    # Update phase to "Processing response..."
                                    phase_label.text = "Processing response..."
                                    ui.update()
                                    
                                    # Display the raw response immediately
                                    with chat_box:
                                        # Remove the spinner row
                                        chat_box.remove(spinner_row)
                                        
                                        # Create a temporary response card
                                        temp_response = ui.card().classes('self-start bg-gray-700 p-3 rounded-lg mb-3 max-w-3/4 border-l-4 border-blue-500')
                                        with temp_response:
                                            ui.markdown(response['text']).classes('text-white')
                                        
                                        # Add a processing indicator
                                        processing_row = ui.row().classes('w-full justify-center my-2')
                                        with processing_row:
                                            ui.spinner('dots', size='sm', color='primary')
                                            ui.label('Processing images and state updates...').classes('text-gray-400 ml-2')
                                    
                                    # Update phase to "Processing images..."
                                    phase_label.text = "Processing images..."
                                    ui.update()
                                    
                                    # Process images and state updates
                                    if response.get("images"):
                                        # Process images directly instead of in a separate function
                                        for image_data in response["images"]:
                                            if isinstance(image_data, dict) and "url" in image_data:
                                                try:
                                                    # Add image to lightbox
                                                    lightbox.add_image(
                                                        thumb_url=image_data["url"],
                                                        orig_url=image_data["url"],
                                                        image_id=image_data.get("id", str(uuid.uuid4())),
                                                        original_prompt=image_data.get("original_prompt", ""),
                                                        parsed_prompt=image_data.get("parsed_prompt", "")
                                                    )
                                                except Exception as e:
                                                    print(f"Error processing image: {str(e)}")
                                    
                                    # Update state displays
                                    if response.get("mood"):
                                        memory_system.update_mood(response["mood"])
                                        mood_display.content = response["mood"]
                                    
                                    if response.get("thoughts"):
                                        for thought in response["thoughts"]:
                                            memory_system.add_thought(thought)
                                        thoughts_display.content = response["thoughts"][-1]
                                    
                                    if response.get("appearance"):
                                        last_appearance = response["appearance"][-1]
                                        appearance_display.content = last_appearance
                                        for appearance in response["appearance"]:
                                            memory_system.add_appearance(appearance)
                                    
                                    if response.get("clothing"):
                                        last_clothing = response["clothing"][-1]
                                        clothing_display.content = last_clothing
                                        for clothing in response["clothing"]:
                                            memory_system.add_clothing(clothing)
                                    
                                    # Update phase to "Finalizing..."
                                    phase_label.text = "Finalizing..."
                                    ui.update()
                                    
                                    # Replace temporary response with final processed version
                                    with chat_box:
                                        # Remove temporary response and processing indicator
                                        chat_box.remove(temp_response)
                                        chat_box.remove(processing_row)
                                        
                                        # Display final processed response
                                        display_message(chat_box, response, memory_system)
                                    
                                    # Update phase to "Done"
                                    phase_label.text = "Done"
                                    ui.update()
                                    
                            except asyncio.TimeoutError:
                                # Handle timeout by showing the partial response if available
                                try:
                                    chat_box.remove(spinner_row)
                                except:
                                    pass
                                with chat_box:
                                    if 'response' in locals():
                                        # Show whatever response we got before timeout
                                        display_message(chat_box, response, memory_system)
                                    else:
                                        ui.label("Response generation timed out. Please try a shorter message.").classes('self-start bg-red-800 p-2 rounded-lg mb-2')
                            except Exception as e:
                                try:
                                    chat_box.remove(spinner_row)
                                except:
                                    pass
                                with chat_box:
                                    ui.label(f"Error: {str(e)}").classes('self-start bg-red-800 p-2 rounded-lg mb-2')
                            finally:
                                send_button.props('disabled=false')
                                is_processing = False
                        
                        # Start the async processing as a background task
                        background_tasks.create(process_message())
                    
                    # Connect send button to function
                    send_button = ui.button('SEND', on_click=send_message)\
                        .props('icon=send').classes('bg-primary text-white px-8')
                    
                    # Allow pressing Enter to send
                    def on_key_press(e):
                        if e.args.get('key') == 'Enter' and not e.args.get('shiftKey'):
                            send_message()
                    
                    msg_input.on('keydown', on_key_press)

        # Right Card
        with ui.card().classes('flex-1 max-w-[768px]'):
            with ui.column().classes('gap-4 w-full'):
                # Location image
                location_image = ui.image('assets/images/location.png').classes('w-full rounded-xl')
                
                # Location description
                location_desc = ui.label('cyberpunk apartment interior at night... synthwave color palette').classes('text-xs text-gray-400')
                
                # Add controls for world management
                ui.button('Change Location', on_click=lambda: ui.notify('Location change functionality to be implemented')).classes('mt-4')

    # Function to toggle test mode - moved inside content() function to fix nonlocal binding
    def toggle_test_mode(value):
        nonlocal test_mode
        test_mode = value
        ui.notify(
            f"Test mode {'enabled' if test_mode else 'disabled'}. " +
            ("Responses will echo input without calling the LLM." if test_mode else "Using normal LLM processing."),
            type='info' if test_mode else 'positive',
            timeout=3000
        )