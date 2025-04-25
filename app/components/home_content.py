"""
Home Content Component
=====================

This module provides the main user interface for the AI assistant.
It includes:
1. Chat interface with message handling
2. Character state display and updates
3. Image generation and display
4. Test mode for development

The component integrates multiple systems including chat pipeline,
memory system, and image generation to create a cohesive experience.
"""


from nicegui import ui, app, events, background_tasks
from ..services.chat_pipeline import ChatPipeline
from ..core.memory_system import MemorySystem
from ..core.state_manager import StateManager
from ..core.response_parser import ResponseParser
from app.services.qdrant_image_store import QdrantImageStore
from app.services.embedder import get_embedder
from app.services.store_images import StoreImages
import httpx
import asyncio
import time
import os
import uuid
import json
import re
import requests

class Lightbox:
    """
    A modal image gallery for previewing and storing generated images.
    
    Features:
    1. Full-screen image viewing
    2. Navigation between images
    3. Basic prompt information display
    4. Image rating and storage in Qdrant
    """
    
    def __init__(self) -> None:
        """
        Initialize the lightbox UI and state.
        
        Creates a full-screen dialog with:
        - Image display area
        - Navigation controls
        - Rating buttons
        - Prompt information display
        """
        # Create a maximized dialog that serves as the lightbox container
        with ui.dialog().props('maximized').classes('bg-black') as self.dialog:
            # Register keyboard event handler for navigation
            ui.keyboard(self._handle_key)
            
            # Main container layout
            with ui.column().classes('w-full h-full items-center justify-between'):
                # Image counter at the top (e.g. "2 / 5")
                self.counter = ui.label().classes('text-white text-h6 mt-2')
                
                # Main content area with navigation controls
                with ui.row().classes('w-full flex-grow'):
                    # Left navigation button
                    with ui.button(on_click=lambda: self._navigate(-1)).props('flat color=white').classes('h-full rounded-none flex items-center justify-center w-16 opacity-70 hover:opacity-100'):
                        ui.icon('chevron_left').classes('text-4xl')
                    
                    # Center image container with proper scaling
                    with ui.column().classes('flex-grow items-center justify-center h-[80vh]'):
                        self.large_image = ui.image().props('no-spinner fit=scale-down').classes('max-h-full max-w-full')
                    
                    # Right navigation button
                    with ui.button(on_click=lambda: self._navigate(1)).props('flat color=white').classes('h-full rounded-none flex items-center justify-center w-16 opacity-70 hover:opacity-100'):
                        ui.icon('chevron_right').classes('text-4xl')
                
                # Bottom information panel
                with ui.column().classes('w-full bg-gray-900 p-2 rounded-t-lg'):
                    # Prompt information display area
                    with ui.row().classes('w-full'):
                        with ui.column().classes('w-full gap-2'):
                            # Original and parsed prompts as markdown
                            self.original_prompt = ui.markdown("").classes('text-white text-sm')
                            self.parsed_prompt = ui.markdown("").classes('text-white text-sm')
                    
                    # Rating buttons row
                    with ui.row().classes('w-full justify-center items-center gap-4 mt-4'):
                        # Positive rating button
                        self.thumbs_up = ui.button(on_click=self._rate_positive).props('flat round color=green').classes('text-2xl')
                        with self.thumbs_up:
                            ui.icon('thumb_up').classes('text-2xl')
                        
                        # Neutral rating button
                        self.neutral = ui.button(on_click=self._rate_neutral).props('flat round color=blue-grey').classes('text-2xl')
                        with self.neutral:
                            ui.icon('thumbs_up_down').classes('text-2xl')
                        
                        # Negative rating button
                        self.thumbs_down = ui.button(on_click=self._rate_negative).props('flat round color=red').classes('text-2xl')
                        with self.thumbs_down:
                            ui.icon('thumb_down').classes('text-2xl')
                        
                        # Status indicator for operations
                        self.status = ui.label("").classes('text-white ml-4')
        
        # Internal state management
        self.image_list = []         # List of image URLs
        self.prompt_list = []        # List of original prompts
        self.parsed_prompt_list = [] # List of parsed prompts
        self.id_list = []            # List of unique image IDs
        self.current_index = 0       # Current image index being viewed
        self.rating = 0              # Current image rating

    def add_image(self, image_url: str, original_prompt: str = "", parsed_prompt: str = "", image_id: str = None) -> None:
        """
        Add an image to the lightbox collection.
        
        Args:
            image_url: URL of the image to add
            original_prompt: Original text that generated the image
            parsed_prompt: Processed prompt used for generation
            image_id: Unique ID for the image (extracts UUID from URL if not provided)
        """
        self.image_list.append(image_url)
        self.prompt_list.append(original_prompt)
        self.parsed_prompt_list.append(parsed_prompt)
        # Extract UUID from the image URL if no ID provided
        if image_id is None:
            try:
                # Extract UUID from URL like: https://im.runware.ai/image/ws/2/ii/3f9a2e89-313f-47b3-a9da-b39ecff1e32a.jpg
                image_id = image_url.split('/')[-1].split('.')[0]
            except:
                image_id = str(uuid.uuid4())  # Fallback to new UUID if extraction fails
        self.id_list.append(image_id)

    def show(self, image_url: str) -> None:
        """
        Display a specific image in the lightbox.
        
        Args:
            image_url: URL of the image to display
        """
        try:
            # Find the index of the image in our collection
            idx = self.image_list.index(image_url)
            self._open(self.image_list[idx])
        except ValueError:
            print(f"Image URL {image_url} not found in lightbox")

    def _handle_key(self, event_args: events.KeyEventArguments) -> None:
        """
        Handle keyboard navigation events.
        
        Args:
            event_args: Keyboard event arguments
        
        Supported keys:
        - Escape: Close the lightbox
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
            direction: Direction to navigate (-1 for previous, 1 for next)
        """
        current_idx = self.current_index
        new_idx = current_idx + direction
        
        # Ensure index is within bounds
        if 0 <= new_idx < len(self.image_list):
            self._open(self.image_list[new_idx])

    def _open(self, url: str) -> None:
        """
        Open and display an image in the lightbox.
        
        Args:
            url: URL of the image to display
        """
        # Set the image source
        self.large_image.set_source(url)
        
        # Update current index and counter
        current_idx = self.image_list.index(url)
        self.current_index = current_idx
        self.counter.text = f'{current_idx + 1} / {len(self.image_list)}'
        
        # Update prompt information
        if current_idx < len(self.prompt_list):
            self.original_prompt.content = f"**Original prompt:** {self.prompt_list[current_idx]}"
        
        if current_idx < len(self.parsed_prompt_list):
            self.parsed_prompt.content = f"**Parsed prompt:** {self.parsed_prompt_list[current_idx]}"
        
        # Open the dialog
        self.dialog.open()

    async def _rate_positive(self):
        """Rate current image positively (+1)."""
        await self._rate_image(1)
    
    async def _rate_neutral(self):
        """Rate current image neutrally (0)."""
        await self._rate_image(0)
    
    async def _rate_negative(self):
        """Rate current image negatively (-1)."""
        await self._rate_image(-1)
        
    async def _rate_image(self, rating_value: int) -> None:
        """
        Store an image rating in Qdrant with full context.
        
        This method first checks if the image already exists in Qdrant and 
        updates the rating if it does. Otherwise, it uses the StoreImages
        service to handle the entire storage pipeline.
        
        Args:
            rating_value: Rating value (-1 for negative, 0 for neutral, 1 for positive)
        """
        try:
            # Get current image information
            current_idx = self.current_index
            if current_idx < 0 or current_idx >= len(self.id_list):
                return
                
            image_id = self.id_list[current_idx]
            image_url = self.image_list[current_idx]
            original_prompt = self.prompt_list[current_idx]
            parsed_prompt = self.parsed_prompt_list[current_idx]
            
            # Determine the appropriate rating message for user feedback
            if rating_value > 0:
                rating_message = "Positively"
            elif rating_value < 0:
                rating_message = "Negatively" 
            else:
                rating_message = "Neutrally"
                
            self.status.text = f"{rating_message} rating image..."
            
            # Get service instances
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
            
            # If update was successful, we're done
            if update_success:
                return
                
            # If image doesn't exist in Qdrant, download it first
            try:
                response = requests.get(image_url)
                response.raise_for_status()
                image_data = response.content
            except Exception as e:
                self.status.text = f"Failed to download image: {str(e)}"
                return
            
            # Create a temporary file for processing
            temp_file = f"temp_{image_id}.jpg"
            try:
                with open(temp_file, 'wb') as f:
                    f.write(image_data)
            except Exception as e:
                self.status.text = f"Failed to save image: {str(e)}"
                return
            
            # Prepare metadata for storage
            metadata = {
                "prompt": parsed_prompt,
                "original_prompt": original_prompt,
                "model": "runware",
                "rating": rating_value
            }
            
            # Use StoreImages service to handle the entire storage pipeline
            result = await image_store.store_image_in_qdrant(
                image_path=temp_file,
                image_id=image_id,
                metadata=metadata
            )
            
            # Clean up temporary file
            try:
                os.remove(temp_file)
            except:
                pass
            
            # Update status based on result
            if result:
                self.status.text = f"Image stored with {rating_value} rating ✓"
            else:
                self.status.text = "Storage failed ✗"
                
        except Exception as e:
            # Log detailed error information
            import traceback
            print(f"Error storing rated image: {str(e)}")
            print(traceback.format_exc())
            self.status.text = f"Error: {str(e)}"

# Initialize the chat pipeline
chat_pipeline = ChatPipeline()

# Helper function to clean response text by removing image tags
def clean_response_text(text):
    """
    Process the main text with [[tag]] markers for UI display.
    
    Converts semantic tags like [[mood]] to UI elements like emojis
    for better visual communication of different content types.
    
    Args:
        text: Raw text with semantic markers
        
    Returns:
        Processed text with UI representations
    """
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
    """
    Display a message in the chat box with proper formatting and tag handling.
    
    This function:
    1. Creates a message container with appropriate styling
    2. Formats and displays the text content
    3. Handles secret/hidden content indicators
    4. Processes and displays generated images
    
    Args:
        chat_box: UI container for messages
        response: Response data including text and images
        memory_system: Reference to the memory system
    """
    # Create a message container for text and related images
    with chat_box:
        with ui.card().classes('self-start bg-gray-700 p-3 rounded-lg mb-3 max-w-3/4 border-l-4 border-blue-500') as card:
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
                    # Create a single lightbox for all images
                    current_lightbox = Lightbox()
                    
                    # Create placeholder arrays to track tasks and containers
                    tasks = []
                    containers = []
                    
                    # FIRST: Create UI containers for all images before any processing
                    for image_data in response["images"]:
                        if isinstance(image_data, dict) and "url" in image_data and "description" in image_data:
                            try:
                                # Build card for each image
                                with ui.card().classes('q-pa-xs'):
                                    # Loading spinner (shown during generation)
                                    loading = ui.spinner('default', size='xl').props('color=primary')
                                    
                                    # Image container (clickable for lightbox)
                                    container = ui.button().props('flat dense').classes('w-[120px] h-[120px] overflow-hidden')
                                    with container:
                                        img = ui.image().props('fit=cover').classes('w-full h-full object-cover')
                                        img.visible = False
                                    
                                    # Description and frame info
                                    with ui.row().classes('items-center justify-between q-mt-xs'):
                                        # Truncate long descriptions
                                        desc = image_data["description"][:30] + "..." if len(image_data["description"]) > 30 else image_data["description"]
                                        ui.label(desc).classes('text-caption text-grey-5 ellipsis')
                                        
                                        # Show frame number if available
                                        orientation = image_data.get("orientation", "")
                                        frame = image_data.get("frame", None)
                                        if orientation or frame:
                                            frame_text = f"[Frame {frame} | {orientation}]" if frame else f"[{orientation}]"
                                            ui.label(frame_text).classes('text-caption text-grey-5')
                                    
                                    # Track task and container for later updates
                                    tasks.append({
                                        'scene': image_data,
                                        'loading': loading,
                                        'img': img,
                                        'button': container
                                    })
                                    containers.append(container)
                            except Exception as e:
                                print(f"Error setting up image display: {str(e)}")
                                ui.notify(f"Error setting up image display: {str(e)}", type='negative')
                    
                    # SECOND: Now update all the images after UI has been created
                    for i, task in enumerate(tasks):
                        try:
                            # Get the current image data
                            current_image = response["images"][i]
                            
                            # Get the original and parsed prompts from the image data
                            scene_data = current_image.get("scene_data", {})
                            original_prompt = scene_data.get("original_text", current_image.get("description", ""))
                            parsed_prompt = scene_data.get("prompt", current_image.get("description", ""))
                            
                            # Add to lightbox
                            current_lightbox.add_image(
                                image_url=current_image["url"],
                                original_prompt=original_prompt,
                                parsed_prompt=parsed_prompt
                            )
                            
                            # Update UI elements
                            task['loading'].visible = False
                            task['img'].set_source(current_image["url"])
                            task['img'].visible = True
                            
                            # Setup lightbox click handler
                            task['button'].on('click', lambda url=current_image["url"]: current_lightbox.show(url))
                        except Exception as e:
                            print(f"Error updating image display: {str(e)}")
                            task['loading'].visible = False
                            ui.label('Display failed').classes('text-caption text-negative')

# Function to check if text contains hidden content tags
def has_hidden_content(text):
    """
    Check if the text contains any secret content tags.
    
    Args:
        text: Text to check for secret markers
        
    Returns:
        bool: True if secret content is present
    """
    return '[[secret]]' in text

def content() -> None:
    """
    Main content function that builds the entire UI.
    
    This function:
    1. Initializes the memory system
    2. Sets up the UI layout with cards
    3. Creates the chat interface
    4. Sets up state displays
    5. Handles message processing
    
    The UI is organized into three main cards:
    - Left: Character information and state
    - Center: Chat interface
    - Right: Location information
    """
    # Initialize memory system
    memory_system = MemorySystem()
    state_manager = StateManager()
    
    # Get initial state from database
    initial_mood = memory_system.get_current_mood()
    initial_thought = state_manager.get_current_thought()
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
        """
        Creates a heartbeat task to keep the connection alive during long operations.
        
        Returns:
            Background task that periodically pings the UI
        """
        async def heartbeat_task():
            """Send small UI updates every few seconds to keep the websocket connection alive."""
            heartbeat_counter = 0
            while is_processing:
                # Just ping with a UI update to keep connection alive
                ui.update()
                heartbeat_counter += 1
                await asyncio.sleep(3)  # Send a heartbeat every 3 seconds
        
        return background_tasks.create(heartbeat_task())
    
    async def set_as_portrait(image_url):
        """
        Copy the image to the portrait location.
        
        Args:
            image_url: URL of the image to set as portrait
        """
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
    
    # Main UI layout with three cards
    with ui.row().classes('w-full gap-4 flex-nowrap'):
        # Left Card - Character Information
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
                    thoughts_display = ui.markdown(initial_thought).classes('text-sm')

        # Center Card - Chat Interface
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
                            """Show help information about test mode."""
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
                    """Show image details in the lightbox."""
                    # Create a new lightbox and add just this image
                    temp_lightbox = Lightbox()
                    temp_lightbox.add_image(
                        image_url=image_data["url"],
                        original_prompt=image_data.get("original_prompt", ""),
                        parsed_prompt=image_data.get("parsed_prompt", "")
                    )
                    
                    # Set the index and open it directly
                    temp_lightbox.current_index = 0
                    
                    # Execute the open function on the UI thread
                    def open_lightbox():
                        temp_lightbox._open()
                    
                    # Run on the UI thread with a small delay
                    ui.timer(0.1, open_lightbox, once=True)
                
                # Message input and send button
                with ui.row().classes('gap-4 mt-auto w-full'):
                    msg_input = ui.textarea(placeholder='Type a message...')\
                        .classes('flex-1 bg-[#1f1f1f] text-white')\
                        .props('auto-grow')
                    
                    def send_message():
                        """
                        Handle the send button click or Enter key.
                        
                        This function:
                        1. Gets the user message
                        2. Prevents multiple submissions
                        3. Displays the user message
                        4. Processes the message in the background
                        5. Handles the response
                        """
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
                            """
                            Process the user message and handle the response.
                            
                            This function:
                            1. Handles test mode responses
                            2. Processes real LLM responses
                            3. Updates the UI with the results
                            4. Manages state changes
                            """
                            nonlocal is_processing
                            # Start a heartbeat to keep connection alive
                            heartbeat_task = setup_heartbeat()
                            
                            try:
                                if test_mode:
                                    # In test mode, create a mock response that echoes the input
                                    # but still process it through the pipeline's response parser
                                    
                                    # First, create the raw mock response that simulates LLM output
                                    raw_mock_response = current_message
                                    
                                    # Create a temporary response container for streaming
                                    with chat_box:
                                        temp_response = ui.card().classes('self-start bg-gray-700 p-3 rounded-lg mb-3 max-w-3/4 border-l-4 border-blue-500')
                                        with temp_response:
                                            streaming_text = ui.markdown("").classes('text-white')
                                    
                                    # Simulate streaming response of the raw text
                                    current_text = ""
                                    words = raw_mock_response.split()
                                    
                                    # Stream words with realistic delays
                                    for word in words:
                                        current_text += word + " "
                                        streaming_text.content = current_text
                                        ui.update()
                                        await asyncio.sleep(0.1)  # 100ms delay between words
                                    
                                    # Update status to show processing
                                    streaming_text.content = current_text + "\n\n*Processing response...*"
                                    
                                    # Process the raw response through the response parser for text content
                                    # while simultaneously processing image content
                                    response_parser = ResponseParser()
                                    
                                    # Look for any image tags in the original message - this is separate from response parsing
                                    image_tags = re.findall(r'(?:<image>|\[\[image\]\])(.*?)(?:</image>|\[\[/image\]\])', current_message, re.DOTALL)
                                    has_images = len(image_tags) > 0
                                    
                                    # Process response through ResponseParser
                                    parsed_response = response_parser.parse_response(raw_mock_response)
                                    
                                    # Log parsed response for debugging
                                    print(f"ResponseParser output: {parsed_response}")
                                    
                                    # Create the mock response based on the parsed output
                                    mock_response = {
                                        'text': parsed_response.get('main_text', raw_mock_response),
                                        'images': []
                                    }
                                    
                                    # Include other elements if present in the parsed response
                                    if 'thoughts' in parsed_response:
                                        mock_response['thoughts'] = parsed_response['thoughts']
                                        
                                    if 'mood' in parsed_response:
                                        mock_response['mood'] = parsed_response['mood']
                                        
                                    if 'appearance' in parsed_response:
                                        mock_response['appearance'] = parsed_response['appearance']
                                        
                                    if 'clothing' in parsed_response:
                                        mock_response['clothing'] = parsed_response['clothing']
                                        
                                    if 'location' in parsed_response:
                                        mock_response['location'] = parsed_response['location']
                                        
                                    # Show the parsed content in the UI
                                    streaming_text.content = clean_response_text(mock_response['text'])
                                    
                                    # Process images if available
                                    image_scenes = []
                                    if has_images:
                                        # Update status in UI
                                        streaming_text.content = clean_response_text(mock_response['text']) + "\n\n*Processing image scenes...*"
                                        
                                        # Create image context for the parser
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
                                        image_scenes = await chat_pipeline.image_scene_parser.parse_images(
                                            json.dumps(image_context),
                                            current_appearance=current_appearance_text
                                        )
                                        
                                        if image_scenes:
                                            # Create UI containers for all images before any processing
                                            with chat_box:
                                                # Create a single lightbox for all images
                                                current_lightbox = Lightbox()
                                                
                                                # Create placeholder arrays to track tasks and containers
                                                tasks = []
                                                containers = []
                                                
                                                # Create UI containers for all images before any processing
                                                for scene in image_scenes:
                                                    try:
                                                        # Build card for each image
                                                        with ui.card().classes('q-pa-xs'):
                                                            # Loading spinner (shown during generation)
                                                            loading = ui.spinner('default', size='xl').props('color=primary')
                                                            
                                                            # Image container (clickable for lightbox)
                                                            container = ui.button().props('flat dense').classes('w-[120px] h-[120px] overflow-hidden')
                                                            with container:
                                                                img = ui.image().props('fit=cover').classes('w-full h-full object-cover')
                                                                img.visible = False
                                                            
                                                            # Description and frame info
                                                            with ui.row().classes('items-center justify-between q-mt-xs'):
                                                                # Truncate long descriptions
                                                                desc = scene.get("content", scene.get("prompt", ""))[:30] + "..." if len(scene.get("content", scene.get("prompt", ""))) > 30 else scene.get("content", scene.get("prompt", ""))
                                                                ui.label(desc).classes('text-caption text-grey-5 ellipsis')
                                                                
                                                                # Show frame number if available
                                                                frame = scene.get("frame", None)
                                                                if frame:
                                                                    ui.label(f"[Frame {frame}]").classes('text-caption text-grey-5')
                                                            
                                                            # Track task and container for later updates
                                                            tasks.append({
                                                                'scene': scene,
                                                                'loading': loading,
                                                                'img': img,
                                                                'button': container
                                                            })
                                                            containers.append(container)
                                                    except Exception as e:
                                                        print(f"Error setting up image display: {str(e)}")
                                                        ui.notify(f"Error setting up image display: {str(e)}", type='negative')
                                            
                                            # Update status to show image generation
                                            streaming_text.content = clean_response_text(mock_response['text']) + "\n\n*Generating images...*"
                                            
                                            # Generate images using the actual generator
                                            image_urls = await chat_pipeline.image_generator.generate(image_scenes)
                                            
                                            # Process results
                                            for i, image_url in enumerate(image_urls):
                                                if image_url:
                                                    # Get the sequence number from the frame field if present, otherwise use index + 1
                                                    sequence = image_scenes[i].get("frame", i + 1)
                                                    try:
                                                        image_uuid = image_url['url'].split('/')[-1].split('.')[0]
                                                    except:
                                                        image_uuid = f"img_{int(time.time())}_{i}"
                                                    
                                                    # Get the original content from the corresponding scene
                                                    original_prompt = image_scenes[i].get("original_text", "")
                                                    parsed_prompt = image_scenes[i].get("prompt", "")
                                                    
                                                    mock_response['images'].append({
                                                        "url": image_url['url'],
                                                        "description": image_scenes[i].get("content", image_scenes[i].get("prompt", "Generated image")),
                                                        "id": image_uuid,
                                                        "sequence": sequence,
                                                        "original_prompt": original_prompt,
                                                        "parsed_prompt": parsed_prompt,
                                                        "scene_data": image_scenes[i]  # Include the full scene data
                                                    })
                                                    
                                                    # Update UI elements
                                                    tasks[i]['loading'].visible = False
                                                    tasks[i]['img'].set_source(image_url['url'])
                                                    tasks[i]['img'].visible = True
                                                    
                                                    # Add to lightbox
                                                    current_lightbox.add_image(
                                                        image_url=image_url['url'],
                                                        original_prompt=original_prompt,
                                                        parsed_prompt=parsed_prompt
                                                    )
                                                    
                                                    # Setup lightbox click handler
                                                    tasks[i]['button'].on('click', lambda url=image_url['url']: current_lightbox.show(url))
                                            
                                            # Create a function to safely display the message on the UI thread
                                            def safe_display():
                                                try:
                                                    # First try to remove the temporary response
                                                    chat_box.remove(temp_response)
                                                except (ValueError, Exception) as e:
                                                    print(f"Error removing temp response: {e}")
                                                    pass
                                                
                                                # Display the final response with images in the correct UI context
                                                with chat_box:
                                                    display_message(chat_box, mock_response, memory_system)
                                            
                                            # Execute the display function on the UI thread with a timer
                                            ui.timer(0.1, safe_display, once=True)
                                        
                                    # No images case is now handled directly in the safe_display function
                                    # Update state displays
                                    if mock_response.get("mood"):
                                        memory_system.update_mood(mock_response["mood"])
                                        mood_display.content = mock_response["mood"]
                                    
                                    if mock_response.get("thoughts"):
                                        for thought in mock_response["thoughts"]:
                                            memory_system.add_thought(thought)
                                            # Update display with the current thought from state manager
                                            thoughts_display.content = memory_system.state_manager.get_current_thought()
                                    
                                    if mock_response.get("appearance"):
                                        for appearance in mock_response["appearance"]:
                                            memory_system.add_appearance(appearance)
                                        # Update with the last appearance
                                        if mock_response["appearance"]:
                                            appearance_display.content = mock_response["appearance"][-1] 
                                    
                                    if mock_response.get("clothing"):
                                        for clothing in mock_response["clothing"]:
                                            memory_system.add_clothing(clothing)
                                        # Update with the last clothing
                                        if mock_response["clothing"]:
                                            clothing_display.content = mock_response["clothing"][-1]
                                    
                                    # Add conversation to memory system (mimicking normal flow)
                                    memory_system.add_conversation_entry("user", current_message)
                                    memory_system.add_conversation_entry("assistant", mock_response["text"])
                                
                                # No images case is now handled directly in the safe_display function
                                # Update state displays
                                if mock_response.get("mood"):
                                    memory_system.update_mood(mock_response["mood"])
                                    mood_display.content = mock_response["mood"]
                                
                                if mock_response.get("thoughts"):
                                    for thought in mock_response["thoughts"]:
                                        memory_system.add_thought(thought)
                                        # Update display with the current thought from state manager
                                        thoughts_display.content = memory_system.state_manager.get_current_thought()
                                
                                if mock_response.get("appearance"):
                                    for appearance in mock_response["appearance"]:
                                        memory_system.add_appearance(appearance)
                                    # Update with the last appearance
                                    if mock_response["appearance"]:
                                        appearance_display.content = mock_response["appearance"][-1] 
                                
                                if mock_response.get("clothing"):
                                    for clothing in mock_response["clothing"]:
                                        memory_system.add_clothing(clothing)
                                    # Update with the last clothing
                                    if mock_response["clothing"]:
                                        clothing_display.content = mock_response["clothing"][-1]
                                
                                # Add conversation to memory system (mimicking normal flow)
                                memory_system.add_conversation_entry("user", current_message)
                                memory_system.add_conversation_entry("assistant", mock_response["text"])
                            
                            except asyncio.TimeoutError:
                                try:
                                    chat_box.remove(temp_response)
                                except (ValueError, NameError):
                                    # Already removed or doesn't exist
                                    pass
                                    
                                chat_box.remove(spinner_row)
                                with chat_box:
                                    ui.label("Response generation timed out. Please try a shorter message.").classes('self-start bg-red-800 p-2 rounded-lg mb-2')
                            except Exception as e:
                                try:
                                    chat_box.remove(temp_response)
                                except (ValueError, NameError):
                                    # Already removed or doesn't exist
                                    pass
                                    
                                if 'spinner_row' in locals():
                                    chat_box.remove(spinner_row)
                                with chat_box:
                                    ui.label(f"Error: {str(e)}").classes('self-start bg-red-800 p-2 rounded-lg mb-2')
                            finally:
                                # Re-enable the send button
                                send_button.props('disabled=false')
                                is_processing = False
                        
                        # Start the async processing as a background task
                        background_tasks.create(process_message())
                    
                    # Connect send button to function
                    send_button = ui.button('SEND', on_click=send_message)\
                        .props('icon=send').classes('bg-primary text-white px-8')
                    
                    # Allow pressing Enter to send
                    def on_key_press(e):
                        """Handle key press events for the input field."""
                        if e.args.get('key') == 'Enter' and not e.args.get('shiftKey'):
                            send_message()
                    
                    msg_input.on('keydown', on_key_press)

        # Right Card - Location Information
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
        """
        Toggle test mode on/off.
        
        Args:
            value: Boolean indicating if test mode should be enabled
        """
        nonlocal test_mode
        test_mode = value
        ui.notify(
            f"Test mode {'enabled' if test_mode else 'disabled'}. " +
            ("Responses will echo input without calling the LLM." if test_mode else "Using normal LLM processing."),
            type='info' if test_mode else 'positive',
            timeout=3000
        )