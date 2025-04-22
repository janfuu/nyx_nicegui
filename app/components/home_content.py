from nicegui import ui, app, events, background_tasks
from ..services.chat_pipeline import ChatPipeline
import time
import asyncio
from ..core.memory_system import MemorySystem
import httpx
import json
from typing import List
import re

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
    """Remove tags from response text while preserving conversation flow"""
    # Define visible tags (these get replaced with placeholders)
    visible_tag_replacements = {
        r'<image>(.*?)</image>': '[Image]'
    }
    
    # Define tags for removable tags (these should be removed from the display)
    removable_tags = ['thought', 'mood', 'appearance', 'clothing', 'location']
    
    # Define tags for special styling (these get styled but kept)
    styled_tags = ['desire', 'internal', 'fantasy', 'hidden', 'private']
    
    # Define hidden tags (these get completely removed)
    hidden_tags = ['secret']
    
    # Replace visible tags with placeholders
    cleaned = text
    for pattern, replacement in visible_tag_replacements.items():
        cleaned = re.sub(pattern, replacement, cleaned, flags=re.DOTALL)
    
    # Process tags that should be removed from display
    for tag in removable_tags:
        # First, handle unclosed tags by closing them
        # Look for an opening tag not followed by a closing tag
        unclosed_pattern = f'<{tag}>(.*?)(?!</{tag}>)(?=<[a-z]+>|[.]|[\n]|$)'
        
        # Find all matches (there could be multiple unclosed tags)
        index_shift = 0
        for match in re.finditer(unclosed_pattern, cleaned, flags=re.DOTALL):
            start_idx = match.start() + index_shift
            end_idx = match.end() + index_shift
            content = match.group(1)
            
            # Close the tag properly by inserting the closing tag
            closing_tag = f'</{tag}>'
            cleaned = cleaned[:end_idx] + closing_tag + cleaned[end_idx:]
            
            # Update the index shift for subsequent matches
            index_shift += len(closing_tag)
            
        # Now handle properly closed tags (which include those we just fixed)
        pattern = f'<{tag}>(.*?)</{tag}>'
        cleaned = re.sub(pattern, '', cleaned, flags=re.DOTALL)
    
    # Process styled tags (keep content but add CSS styling)
    for tag in styled_tags:
        # First, handle unclosed tags by closing them
        unclosed_pattern = f'<{tag}>(.*?)(?!</{tag}>)(?=<[a-z]+>|[.]|[\n]|$)'
        
        # Find all matches (there could be multiple unclosed tags)
        index_shift = 0
        for match in re.finditer(unclosed_pattern, cleaned, flags=re.DOTALL):
            start_idx = match.start() + index_shift
            end_idx = match.end() + index_shift
            
            # Close the tag properly by inserting the closing tag
            closing_tag = f'</{tag}>'
            cleaned = cleaned[:end_idx] + closing_tag + cleaned[end_idx:]
            
            # Update the index shift for subsequent matches
            index_shift += len(closing_tag)
        
        # Now handle properly closed tags (which include those we just fixed)
        pattern = f'<{tag}>(.*?)</{tag}>'
        # Replace with styled span
        replacement = f'<span class="styled-tag {tag}">\\1</span>'
        cleaned = re.sub(pattern, replacement, cleaned, flags=re.DOTALL)
    
    # Process hidden tags
    for tag in hidden_tags:
        # First, handle unclosed tags by closing them
        unclosed_pattern = f'<{tag}>(.*?)(?!</{tag}>)(?=<[a-z]+>|[.]|[\n]|$)'
        
        # Find all matches (there could be multiple unclosed tags)
        index_shift = 0
        for match in re.finditer(unclosed_pattern, cleaned, flags=re.DOTALL):
            start_idx = match.start() + index_shift
            end_idx = match.end() + index_shift
            
            # Close the tag properly by inserting the closing tag
            closing_tag = f'</{tag}>'
            cleaned = cleaned[:end_idx] + closing_tag + cleaned[end_idx:]
            
            # Update the index shift for subsequent matches
            index_shift += len(closing_tag)
        
        # Now handle properly closed tags (which include those we just fixed)
        pattern = f'<{tag}>(.*?)</{tag}>'
        cleaned = re.sub(pattern, '', cleaned, flags=re.DOTALL)
    
    return cleaned

# Function to check if text contains hidden content tags
def has_hidden_content(text):
    """Check if the text contains any secret content tags"""
    # Only secret tags are completely hidden now
    hidden_tags = ['secret']
    
    # Check for each tag type
    for tag in hidden_tags:
        pattern = f'<{tag}>(.*?)</{tag}>'
        if re.search(pattern, text, re.DOTALL):
            return True
    
    return False

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
                                ui.label('Thinking...').classes('text-gray-400 ml-2')
                        
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
                                    # Extract all types of tags
                                    image_tags = re.findall(r'<image>(.*?)</image>', current_message, re.DOTALL)
                                    thought_tags = re.findall(r'<thought>(.*?)</thought>', current_message, re.DOTALL)
                                    mood_tags = re.findall(r'<mood>(.*?)</mood>', current_message, re.DOTALL)
                                    appearance_tags = re.findall(r'<appearance>(.*?)</appearance>', current_message, re.DOTALL)
                                    location_tags = re.findall(r'<location>(.*?)</location>', current_message, re.DOTALL)
                                    clothing_tags = re.findall(r'<clothing>(.*?)</clothing>', current_message, re.DOTALL)
                                    
                                    # Also look for secret tags that will be hidden but indicated with a lock icon
                                    secret_tags = re.findall(r'<secret>(.*?)</secret>', current_message, re.DOTALL)
                                    desire_tags = re.findall(r'<desire>(.*?)</desire>', current_message, re.DOTALL)
                                    internal_tags = re.findall(r'<internal>(.*?)</internal>', current_message, re.DOTALL)
                                    
                                    # Create a mock response with only the tags that were included
                                    mock_response = {
                                        'text': f"Echo: {current_message}",
                                        'images': []
                                    }
                                    
                                    # Only include thoughts if thought tags were found
                                    if thought_tags:
                                        mock_response['thoughts'] = thought_tags
                                        # Store thoughts in test mode too
                                        for thought in thought_tags:
                                            memory_system.add_thought(thought)
                                    
                                    # Only include mood if mood tags were found
                                    if mood_tags:
                                        mock_response['mood'] = mood_tags[0]  # Only use the first mood tag
                                        # Store mood in test mode too
                                        memory_system.update_mood(mood_tags[0])
                                    
                                    # Only include appearance if appearance tags were found
                                    if appearance_tags:
                                        mock_response['appearance'] = appearance_tags
                                        # Store appearance changes in test mode too
                                        for appearance in appearance_tags:
                                            memory_system.add_appearance(appearance)
                                            
                                        # Update the display with most recent appearance from database 
                                        # to ensure consistency between components
                                        current_appearances = memory_system.get_recent_appearances(1)
                                        if current_appearances:
                                            appearance_display.content = current_appearances[0]["description"]
                                        else:
                                            # Fallback to the most recent tag if database query fails
                                            appearance_display.content = appearance_tags[-1]
                                    
                                    # Only include clothing if clothing tags were found
                                    if clothing_tags:
                                        mock_response['clothing'] = clothing_tags
                                        # Store clothing changes in test mode too
                                        for clothing in clothing_tags:
                                            memory_system.add_clothing(clothing)
                                            
                                        # Update the display with most recent clothing from database 
                                        # to ensure consistency between components
                                        current_clothing = memory_system.get_recent_clothing(1)
                                        if current_clothing:
                                            clothing_display.content = current_clothing[0]["description"]
                                        else:
                                            # Fallback to the most recent tag if database query fails
                                            clothing_display.content = clothing_tags[-1]
                                        
                                        has_clothing_update = True
                                    else:
                                        has_clothing_update = False
                                    
                                    # Only include location if location tags were found
                                    if location_tags:
                                        mock_response['location'] = location_tags[0]  # Only use the first location tag
                                        # Store location in test mode too
                                        memory_system.update_location(location_tags[0])
                                    
                                    # If image tags were found, create mock image data
                                    if image_tags:
                                        # Use nyx_avatar.png for all placeholders but ensure unique URLs for navigation
                                        avatar_path = '/assets/images/nyx_avatar.png'
                                        
                                        # Create mock image entries for each tag
                                        for i, tag in enumerate(image_tags):
                                            # Add a query parameter to make each URL unique
                                            unique_url = f"{avatar_path}?id={i}"
                                            mock_response['images'].append({
                                                'url': unique_url,  # Use unique URLs for each image
                                                'description': tag.strip(),
                                                'original_prompt': tag.strip(),
                                                'parsed_prompt': f"Parsed version of: {tag.strip()}"
                                            })
                                    
                                    response = mock_response
                                else:
                                    # Get LLM response with timeout in normal mode
                                    response = await asyncio.wait_for(
                                        chat_pipeline.process_message(current_message),
                                        timeout=90  # 90 second timeout for LLM response
                                    )
                                    
                                    # Ensure mood, thoughts, and appearance are properly processed
                                    # The chat_pipeline should handle this, but let's make sure
                                    if response.get("mood"):
                                        memory_system.update_mood(response["mood"])
                                    
                                    if response.get("thoughts"):
                                        for thought in response["thoughts"]:
                                            memory_system.add_thought(thought)
                                    
                                    if response.get("appearance"):
                                        # First update display with the latest appearance from the response
                                        last_appearance = response["appearance"][-1]
                                        appearance_display.content = last_appearance
                                        has_appearance_update = True
                                        
                                        # Store appearances in the database - this should already be handled by chat_pipeline
                                        # but let's make sure that our UI reflects the changes
                                        for appearance in response["appearance"]:
                                            memory_system.add_appearance(appearance)
                                        
                                        # Force a UI update to ensure the appearance display is refreshed
                                        ui.update()
                                    else:
                                        # Check for unclosed appearance tags and close them
                                        # First fix the response text by closing any unclosed tags
                                        appearance_pattern = r'<appearance>(.*?)(?!</appearance>)(?=<[a-z]+>|\.|[\n]|$)'
                                        fixed_text = response['text']
                                        
                                        # Find all matches (there could be multiple unclosed tags)
                                        index_shift = 0
                                        for match in re.finditer(appearance_pattern, fixed_text, flags=re.DOTALL):
                                            start_idx = match.start() + index_shift
                                            end_idx = match.end() + index_shift
                                            content = match.group(1)
                                            
                                            # Close the tag properly by inserting the closing tag
                                            closing_tag = '</appearance>'
                                            fixed_text = fixed_text[:end_idx] + closing_tag + fixed_text[end_idx:]
                                            
                                            # Save this content to the database and update the UI
                                            if content.strip():
                                                memory_system.add_appearance(content.strip())
                                                appearance_display.content = content.strip()
                                                has_appearance_update = True
                                                print(f"Found and closed unclosed appearance tag with content: '{content.strip()}'")
                                            
                                            # Update the index shift for subsequent matches
                                            index_shift += len(closing_tag)
                                        
                                        # If we didn't find any unclosed tags and didn't process any updates above
                                        if not has_appearance_update:
                                            # Try looking for the properly closed tags in case previous code missed them
                                            appearance_content = re.findall(r'<appearance>(.*?)</appearance>', fixed_text, re.DOTALL)
                                            if appearance_content:
                                                for appearance in appearance_content:
                                                    # Check if this is a meaningful non-empty appearance update
                                                    if appearance.strip():
                                                        memory_system.add_appearance(appearance.strip())
                                                        appearance_display.content = appearance.strip()
                                                        has_appearance_update = True
                                            else:
                                                has_appearance_update = False
                                    
                                    if response.get("clothing"):
                                        # Get the last clothing entry (most recent)
                                        last_clothing = response["clothing"][-1]
                                        print(f"Updating clothing display with: '{last_clothing}'")
                                        clothing_display.content = last_clothing
                                        has_clothing_update = True
                                        
                                        # Store clothing in the database
                                        for clothing in response["clothing"]:
                                            memory_system.add_clothing(clothing)
                                        
                                        # Force a UI update to ensure the clothing display is refreshed
                                        ui.update()
                                    else:
                                        # Check for unclosed clothing tags and close them
                                        # First fix the response text by closing any unclosed tags
                                        clothing_pattern = r'<clothing>(.*?)(?!</clothing>)(?=<[a-z]+>|\.|[\n]|$)'
                                        if 'fixed_text' not in locals():
                                            fixed_text = response['text']
                                        
                                        # Find all matches (there could be multiple unclosed tags)
                                        index_shift = 0
                                        for match in re.finditer(clothing_pattern, fixed_text, flags=re.DOTALL):
                                            start_idx = match.start() + index_shift
                                            end_idx = match.end() + index_shift
                                            content = match.group(1)
                                            
                                            # Close the tag properly by inserting the closing tag
                                            closing_tag = '</clothing>'
                                            fixed_text = fixed_text[:end_idx] + closing_tag + fixed_text[end_idx:]
                                            
                                            # Save this content to the database and update the UI
                                            if content.strip():
                                                memory_system.add_clothing(content.strip())
                                                clothing_display.content = content.strip()
                                                has_clothing_update = True
                                                print(f"Found and closed unclosed clothing tag with content: '{content.strip()}'")
                                            
                                            # Update the index shift for subsequent matches
                                            index_shift += len(closing_tag)
                                        
                                        # If we didn't find any unclosed tags and didn't process any updates above
                                        if not has_clothing_update:
                                            # Try looking for the properly closed tags in case previous code missed them
                                            clothing_content = re.findall(r'<clothing>(.*?)</clothing>', fixed_text, re.DOTALL)
                                            if clothing_content:
                                                for clothing in clothing_content:
                                                    # Check if this is a meaningful non-empty clothing update
                                                    if clothing.strip():
                                                        memory_system.add_clothing(clothing.strip())
                                                        clothing_display.content = clothing.strip()
                                                        has_clothing_update = True
                                            else:
                                                has_clothing_update = False
                                        
                                        # Update the response text with our fixed version that has properly closed tags
                                        response['text'] = fixed_text
                                
                                if response.get("location"):
                                    has_location_update = True
                                    # Get the current location from database to ensure UI is in sync
                                    current_locations = memory_system.get_recent_locations(1)
                                    if current_locations and location_desc:
                                        location_desc.content = current_locations[0]["description"]
                                else:
                                    has_location_update = False
                                
                                # Final check to ensure UI displays are in sync with database state
                                # This ensures any state changes applied by the pipeline are reflected in the UI
                                current_appearances = memory_system.get_recent_appearances(1)
                                if current_appearances:
                                    appearance_display.content = current_appearances[0]["description"]
                                    
                                current_clothing = memory_system.get_recent_clothing(1)
                                if current_clothing:
                                    clothing_display.content = current_clothing[0]["description"]
                                
                                # Display assistant response with original formatting
                                with chat_box:
                                    # Remove the spinner row before showing the response
                                    chat_box.remove(spinner_row)
                                    
                                    # Create a message container for text and related images
                                    with ui.card().classes('self-start bg-gray-700 p-3 rounded-lg mb-3 max-w-3/4 border-l-4 border-blue-500'):
                                        # Clean response text by removing image tags before displaying
                                        cleaned_text = clean_response_text(response['text'])
                                        ui.markdown(cleaned_text).classes('text-white')
                                        
                                        # Add indicator for hidden content if present
                                        if has_hidden_content(response['text']):
                                            with ui.row().classes('justify-end items-center mt-1'):
                                                ui.icon('lock', color='grey').classes('text-xs')
                                        
                                        # Update the side panels with thoughts, mood, and appearance
                                        # But don't display them in the chat response anymore
                                        has_updates = False
                                        
                                        if response.get("thoughts"):
                                            for thought in response["thoughts"]:
                                                thoughts_display.content = thought
                                            has_thoughts_update = True
                                        else:
                                            has_thoughts_update = False
                                        
                                        if response.get("mood"):
                                            mood_display.content = response["mood"]
                                            has_mood_update = True
                                        else:
                                            has_mood_update = False
                                        
                                        # Add back the clothing update code that was removed
                                        if response.get("clothing"):
                                            # Get the last clothing entry (most recent)
                                            last_clothing = response["clothing"][-1]
                                            print(f"Updating clothing display in UI section with: '{last_clothing}'")
                                            clothing_display.content = last_clothing
                                            has_clothing_update = True
                                        else:
                                            has_clothing_update = False
                                        
                                        # Add status indicators if any updates exist
                                        has_updates = has_thoughts_update or has_mood_update or has_appearance_update or has_location_update or has_clothing_update
                                        
                                        if has_updates:
                                            ui.separator().classes('my-2')
                                            with ui.row().classes('justify-end items-center gap-2 mt-2'):
                                                ui.label("Updates:").classes('text-xs text-gray-400')
                                                
                                                if has_thoughts_update:
                                                    ui.icon('psychology', color='purple').classes('text-lg')
                                                
                                                if has_mood_update:
                                                    ui.icon('mood', color='blue').classes('text-lg')
                                                
                                                if has_appearance_update:
                                                    ui.icon('face', color='pink').classes('text-lg')
                                                
                                                if has_clothing_update:
                                                    ui.icon('checkroom', color='pink').classes('text-lg')
                                                
                                                if has_location_update:
                                                    ui.icon('place', color='green').classes('text-lg')
                                        
                                        # Display generated images if present
                                        if response.get("images") and len(response["images"]) > 0:
                                            ui.separator().classes('my-2')
                                            with ui.row().classes('q-gutter-sm flex-wrap justify-center'):
                                                # Create a list to store image generation tasks
                                                tasks = []
                                                containers = []
                                                
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
                                                        
                                                        # Get the original prompt from the image tags in the raw response text
                                                        image_tags = re.findall(r'<image>(.*?)</image>', response['text'], re.DOTALL)
                                                        original_prompt = ""
                                                        if i < len(image_tags):
                                                            original_prompt = image_tags[i].strip()
                                                        else:
                                                            # Fallback to the description if image tags can't be found
                                                            original_prompt = current_image.get("description", "")
                                                            
                                                        # Add to lightbox with prompts
                                                        lightbox.add_image(
                                                            thumb_url=current_image["url"],
                                                            orig_url=current_image["url"],
                                                            image_id=image_uuid,
                                                            original_prompt=original_prompt,
                                                            parsed_prompt=current_image.get("parsed_prompt", current_image.get("description", ""))
                                                        )
                                                        
                                                        # Set up click handler - update to use the lightbox
                                                        task['button'].on('click', lambda url=current_image["url"]: lightbox._open(url))
                                                    except Exception as e:
                                                        print(f"Error updating image display: {str(e)}")
                                                        task['loading'].visible = False
                                                        ui.label('Display failed').classes('text-caption text-negative')
                                        
                                        # Add Regenerate button for re-running image generation
                                        # Only show if there are images to regenerate
                                        if response.get("images") and len(response["images"]) > 0:
                                            ui.separator().classes('my-2')
                                            with ui.row().classes('justify-between w-full'):
                                                regenerate_button = ui.button('Regenerate Images', icon='refresh')\
                                                    .props('color=purple').classes('mr-2')
                                                
                                                async def regenerate_images():
                                                    nonlocal is_processing
                                                    
                                                    # Prevent multiple submissions while processing
                                                    if is_processing:
                                                        ui.notify('Still processing, please wait...', color='warning')
                                                        return
                                                    
                                                    # Set processing flag
                                                    is_processing = True
                                                    
                                                    # Show regeneration is happening
                                                    regenerate_button.props('loading')
                                                    
                                                    # Add visible spinner to chat box
                                                    with chat_box:
                                                        regen_spinner_row = ui.row().classes('w-full justify-center my-4')
                                                        with regen_spinner_row:
                                                            ui.spinner('dots', size='lg', color='purple')
                                                            ui.label('Regenerating images...').classes('text-gray-400 ml-2')
                                                    
                                                    ui.update()
                                                    
                                                    # Start a heartbeat to keep connection alive
                                                    heartbeat_task = setup_heartbeat()
                                                    
                                                    try:
                                                        # Get current appearance and mood for context
                                                        current_appearance = memory_system.get_recent_appearances(1)
                                                        current_appearance_text = current_appearance[0]["description"] if current_appearance else None
                                                        current_mood = memory_system.get_current_mood()
                                                        current_location = memory_system.get_recent_locations(1)
                                                        current_location_text = current_location[0]["description"] if current_location else None
                                                        
                                                        # Extract image tags from response
                                                        image_pattern = r'<image>(.*?)</image>'
                                                        image_tags = re.findall(image_pattern, response['text'], re.DOTALL)
                                                        
                                                        if not image_tags:
                                                            ui.notify('No <image> tags found in the response', color='warning')
                                                            # Remove spinner
                                                            chat_box.remove(regen_spinner_row)
                                                            regenerate_button.props('loading=false')
                                                            is_processing = False
                                                            return
                                                        
                                                        # Format image contents with context and sequence
                                                        image_context = {
                                                            "appearance": current_appearance_text,
                                                            "mood": current_mood,
                                                            "location": current_location_text,
                                                            "images": [{"content": tag.strip(), "sequence": i+1} for i, tag in enumerate(image_tags)]
                                                        }
                                                        
                                                        # Process through image parser
                                                        try:
                                                            # Use timeout for parser
                                                            parsed_scenes = await asyncio.wait_for(
                                                                chat_pipeline.image_scene_parser.parse_images(
                                                                    json.dumps(image_context),
                                                                    current_appearance=current_appearance_text
                                                                ),
                                                                timeout=60  # 60 second timeout for scene parsing
                                                            )
                                                        except asyncio.TimeoutError:
                                                            ui.notify('Image scene parsing timed out. Please try again.', color='warning')
                                                            # Remove spinner
                                                            chat_box.remove(regen_spinner_row)
                                                            regenerate_button.props('loading=false')
                                                            is_processing = False
                                                            return
                                                        except Exception as e:
                                                            ui.notify(f'Error parsing image scenes: {str(e)}', color='negative')
                                                            # Remove spinner
                                                            chat_box.remove(regen_spinner_row)
                                                            regenerate_button.props('loading=false')
                                                            is_processing = False
                                                            return
                                                        
                                                        if parsed_scenes:
                                                            # Generate all images in parallel
                                                            scene_contents = [{"prompt": scene["prompt"], "orientation": scene["orientation"]} for scene in parsed_scenes]
                                                            print(f"Generating {len(scene_contents)} images in parallel...")
                                                            
                                                            try:
                                                                # Generate all images at once with timeout
                                                                image_urls = await asyncio.wait_for(
                                                                    chat_pipeline.image_generator.generate(scene_contents),
                                                                    timeout=90  # 90 second timeout for all images
                                                                )
                                                            except asyncio.TimeoutError:
                                                                ui.notify('Image generation timed out. Please try again.', color='warning')
                                                                # Remove spinner
                                                                chat_box.remove(regen_spinner_row)
                                                                regenerate_button.props('loading=false')
                                                                is_processing = False
                                                                return
                                                            except Exception as e:
                                                                ui.notify(f'Error generating images: {str(e)}', color='negative')
                                                                # Remove spinner
                                                                chat_box.remove(regen_spinner_row)
                                                                regenerate_button.props('loading=false')
                                                                is_processing = False
                                                                return
                                                            
                                                            # Remove spinner now that we have images
                                                            try:
                                                                chat_box.remove(regen_spinner_row)
                                                            except Exception:
                                                                # Already removed - ignore
                                                                pass
                                                            
                                                            if image_urls and len(image_urls) > 0:
                                                                # Clear existing images - use a safer approach
                                                                # Instead of removing old elements, we'll just create a fresh expansion
                                                                expansion_id = "regenerated_images_expansion"
                                                                
                                                                # Display regenerated images in a new expansion
                                                                with ui.expansion('GENERATED IMAGES', icon='image').classes('w-full').props(f'id={expansion_id}'):
                                                                    with ui.row().classes('flex-wrap gap-2 w-full'):
                                                                        # Create a list of tuples with original tag, parsed scene, and image URL
                                                                        image_data = list(zip(image_tags, parsed_scenes, image_urls))
                                                                        # Sort by sequence number if available
                                                                        image_data.sort(key=lambda x: x[1].get('sequence', 0) if isinstance(x[1], dict) else 0)
                                                                        
                                                                        for original_tag, scene, image_url in image_data:
                                                                            if image_url:
                                                                                with ui.card().classes('w-[120px] p-1 bg-gray-800'):
                                                                                    # Extract UUID from URL path for image ID
                                                                                    try:
                                                                                        # Use a unique UUID instead of extracting from filename
                                                                                        import uuid
                                                                                        image_uuid = str(uuid.uuid4())
                                                                                    except:
                                                                                        # Fallback with a proper UUID
                                                                                        import uuid
                                                                                        image_uuid = str(uuid.uuid4())
                                                                                    
                                                                                    # Get scene prompt if available
                                                                                    parsed_prompt = scene.get('prompt', '') if isinstance(scene, dict) else str(scene)
                                                                                    
                                                                                    # Add to lightbox with ID and prompts
                                                                                    img = lightbox.add_image(
                                                                                        thumb_url=image_url,
                                                                                        orig_url=image_url,
                                                                                        image_id=image_uuid,
                                                                                        original_prompt=original_tag,
                                                                                        parsed_prompt=parsed_prompt
                                                                                    )
                                                                                    img.classes('w-full rounded-lg cursor-pointer')
                                                                                    
                                                                                    with ui.row().classes('items-center justify-between w-full mt-1'):
                                                                                        short_desc = original_tag[:30] + ("..." if len(original_tag) > 30 else original_tag)
                                                                                        ui.label(short_desc).classes('text-xs italic text-gray-300 truncate max-w-[75%]')
                                                                                        ui.button(icon='search', on_click=lambda url=image_url, tag=original_tag: show_image_details({"url": url, "description": tag}))\
                                                                                            .props('flat dense round').classes('text-xs')
                                                            else:
                                                                ui.notify('Failed to generate images', color='negative')
                                                        else:
                                                            # Remove spinner
                                                            chat_box.remove(regen_spinner_row)
                                                            ui.notify('No visual scenes found in the response', color='warning')
                                                    except Exception as e:
                                                        ui.notify(f'Failed to generate images: {str(e)}', color='negative', timeout=5000)
                                                    finally:
                                                        # In case spinner wasn't removed in one of the error paths
                                                        try:
                                                            chat_box.remove(regen_spinner_row)
                                                        except:
                                                            pass
                                                        regenerate_button.props('loading=false')
                                                        is_processing = False
                                                
                                                regenerate_button.on('click', regenerate_images)
                                
                            except asyncio.TimeoutError:
                                # Handle timeout
                                chat_box.remove(spinner_row)
                                with chat_box:
                                    ui.label("Sorry, I'm taking too long to respond. Please try again.").classes('self-start bg-red-800 p-2 rounded-lg mb-2')
                                ui.notify("Request timed out", color="negative")
                            except Exception as e:
                                # Handle errors
                                chat_box.remove(spinner_row)
                                with chat_box:
                                    ui.label(f"Error: {str(e)}").classes('self-start bg-red-800 p-2 rounded-lg mb-2')
                                ui.notify(f"Error processing message: {str(e)}", color="negative")
                                    
                            finally:
                                # Re-enable the send button
                                send_button.props('disabled=false')
                                # Reset processing flag
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