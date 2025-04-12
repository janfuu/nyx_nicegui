from nicegui import ui
from ..services.chat_pipeline import ChatPipeline
import time
import asyncio

# Initialize the chat pipeline
chat_pipeline = ChatPipeline()

def content() -> None:
    with ui.row().classes('w-full gap-4 flex-nowrap'):
        # Left Card
        with ui.card().classes('flex-1'):
            with ui.column().classes('gap-4 w-full'):
                ui.image('assets/images/portrait.jpg').classes('w-full rounded-xl')
                
                # Character's current mood display
                ui.label('MOOD').classes('text-blue-500 text-sm')
                with ui.card().classes('bg-[#1a1a1a] p-3 rounded w-full'):
                    mood_display = ui.markdown("Neutral").classes('text-sm')

                # Character's current appearance display
                ui.label('APPEARANCE').classes('text-purple-500 text-sm')
                with ui.card().classes('bg-[#1a1a1a] p-3 rounded w-full'):
                    appearance_display = ui.markdown("A young woman with cybernetic enhancements, circuits glowing faintly beneath her skin...").classes('text-sm')

                # Character's thoughts display
                ui.label('THOUGHTS').classes('text-gray-500 text-sm')
                with ui.card().classes('bg-[#1a1a1a] p-3 rounded w-full'):
                    thoughts_display = ui.markdown("It's... unusual to be addressed so familiarly...").classes('text-sm')

        # Center Card
        with ui.card().classes('flex-2 w-[800px]'):
            with ui.column().classes('h-full w-full gap-4'):
                # Chat display area - use a simple scrollable container
                chat_container = ui.scroll_area().classes('h-[600px] w-full')
                with chat_container:
                    chat_box = ui.column().classes('p-6 bg-[#1a1a1a] rounded w-full')
                
                # Function to display image details
                def show_image_details(image_data):
                    dialog = ui.dialog()
                    with dialog:
                        with ui.card().classes('w-full max-w-3xl'):
                            ui.label('Image Details').classes('text-xl font-bold mb-2')
                            ui.image(image_data["url"]).classes('w-full rounded-lg mb-4')
                            ui.label('Original Prompt:').classes('font-bold')
                            ui.markdown(image_data["description"]).classes('bg-[#1a1a1a] p-3 rounded mb-4')
                            ui.button('Close', on_click=dialog.close).classes('self-end')
                    dialog.open()
                
                # Message input and send button
                with ui.row().classes('gap-4 mt-auto w-full'):
                    msg_input = ui.input(placeholder='Type a message...').classes('flex-1 bg-[#1f1f1f] text-white')
                    thinking_indicator = ui.spinner('Thinking...').classes('hidden')
                    
                    def send_message():
                        """Handle the send button click or Enter key"""
                        user_message = msg_input.value
                        if not user_message.strip():
                            return
                        
                        # Clear input immediately
                        current_message = user_message
                        msg_input.value = ""
                        
                        # Display user message immediately
                        with chat_box:
                            user_msg = ui.label(f"You: {current_message}").classes('self-end bg-blue-800 p-2 rounded-lg mb-2 max-w-3/4')
                        
                        # Ensure UI updates before continuing
                        ui.update()
                        
                        # Show thinking indicator
                        thinking_indicator.classes('inline-block')
                        ui.update()  # Force UI update again to show the spinner
                        
                        async def process_message():
                            try:
                                response = await chat_pipeline.process_message(current_message)
                                
                                # Display assistant response
                                with chat_box:
                                    # Create a message container for text and related images
                                    with ui.card().classes('self-start bg-gray-700 p-3 rounded-lg mb-3 max-w-3/4 border-l-4 border-blue-500'):
                                        # First show the text response with markdown formatting
                                        ui.markdown(response['text']).classes('text-white')
                                        
                                        # Display any thoughts in a subtle way
                                        if response.get("thoughts") and len(response["thoughts"]) > 0:
                                            ui.separator().classes('my-2')
                                            with ui.expansion('THOUGHTS', icon='psychology').classes('w-full'):
                                                for thought in response["thoughts"]:
                                                    ui.markdown(f"*{thought}*").classes('text-gray-300 text-sm italic pl-4')
                                                    # Update the thoughts display with the most recent thought
                                                    thoughts_display.content = thought
                                        
                                        # Display mood update
                                        if response.get("mood"):
                                            ui.separator().classes('my-2')
                                            with ui.expansion('MOOD', icon='mood').classes('w-full'):
                                                ui.markdown(f"*{response['mood']}*").classes('text-blue-300 text-sm italic pl-4')
                                        
                                        # Display any self actions (appearance updates)
                                        if response.get("self") and len(response["self"]) > 0:
                                            ui.separator().classes('my-2')
                                            with ui.expansion('APPEARANCE', icon='face').classes('w-full'):
                                                for self_action in response["self"]:
                                                    ui.markdown(f"*{self_action}*").classes('text-purple-300 text-sm italic pl-4')
                                        
                                        # Display any generated images right below the text
                                        if response.get("images") and len(response["images"]) > 0:
                                            ui.separator().classes('my-2')
                                            ui.label("Generated images:").classes('text-xs text-blue-300 mb-1')
                                            
                                            with ui.row().classes('flex-wrap gap-2 w-full'):
                                                for idx, image_data in enumerate(response["images"]):
                                                    # Create a container for each image and its controls
                                                    with ui.card().classes('w-[180px] p-1 bg-gray-800'):
                                                        # Display the image
                                                        img = ui.image(image_data["url"]).classes('w-full rounded-lg cursor-pointer')
                                                        img.on('click', lambda d=image_data: show_image_details(d))
                                                        
                                                        # Image caption with preview option
                                                        with ui.row().classes('items-center justify-between w-full mt-1'):
                                                            short_desc = image_data["description"][:30] + ("..." if len(image_data["description"]) > 30 else "")
                                                            ui.label(short_desc).classes('text-xs italic text-gray-300 truncate max-w-[75%]')
                                                            ui.button(icon='search', on_click=lambda d=image_data: show_image_details(d))\
                                                                .props('flat dense round').classes('text-xs')
                                
                                # Update mood display if provided
                                if response.get("mood"):
                                    mood_display.content = response["mood"]
                                
                                # Update appearance display if provided
                                if response.get("self") and len(response["self"]) > 0:
                                    appearance_display.content = response["self"][-1]  # Show the most recent appearance update
                                    
                            except Exception as e:
                                # Handle errors
                                with chat_box:
                                    ui.label(f"Error: {str(e)}").classes('self-start bg-red-800 p-2 rounded-lg mb-2')
                                    
                            finally:
                                # Hide thinking indicator when done
                                thinking_indicator.classes('hidden')
                        
                        # Start the async processing
                        ui.timer(0.1, lambda: asyncio.create_task(process_message()), once=True)
                    
                    # Connect send button to function
                    send_button = ui.button('SEND', on_click=send_message)\
                        .props('icon=send').classes('bg-primary text-white px-8')
                    
                    # Allow pressing Enter to send
                    def on_key_press(e):
                        if e.args.get('key') == 'Enter' and not e.args.get('shiftKey'):
                            send_message()
                    
                    msg_input.on('keydown', on_key_press)

        # Right Card
        with ui.card().classes('flex-1'):
            with ui.column().classes('gap-4 w-full'):
                # Location image
                location_image = ui.image('assets/images/location.png').classes('w-full rounded-xl')
                
                # Location description
                location_desc = ui.label('cyberpunk apartment interior at night... synthwave color palette').classes('text-xs text-gray-400')
                
                # Add controls for world management
                ui.button('Change Location', on_click=lambda: ui.notify('Location change functionality to be implemented')).classes('mt-4')