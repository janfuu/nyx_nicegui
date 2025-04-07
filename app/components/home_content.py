import time
from nicegui import ui, app
from ..services.chat_pipeline import ChatPipeline

# Initialize the chat pipeline
chat_pipeline = ChatPipeline()

def content() -> None:
    with ui.row().classes('w-full gap-4 flex-nowrap'):
        # Left Card
        with ui.card().classes('flex-1'):
            with ui.column().classes('gap-4 w-full'):
                ui.image('assets/images/portrait.jpg').classes('w-full rounded-xl')
                
                # Character's current mood display
                mood_display = ui.textarea(value="It's... unusual to be addressed so familiarly...").props('readonly auto-grow')\
                    .classes('bg-[#1a1a1a] rounded p-2 text-sm w-full')
                
                mood_label = ui.label('mood').classes('text-blue-500')

        # Center Card
        with ui.card().classes('flex-2 w-[800px]'):
            with ui.column().classes('h-full w-full gap-4'):
                # Chat display area
                chat_box = ui.column().classes('h-[600px] overflow-y-auto bg-[#1a1a1a] p-6 rounded w-full')
                
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
                    
                    def send_message():
                        user_message = msg_input.value
                        if not user_message.strip():
                            return
                        
                        # Display user message
                        with chat_box:
                            ui.label(f"You: {user_message}").classes('self-end bg-blue-800 p-2 rounded-lg mb-2 max-w-3/4')
                        
                        # Clear input
                        msg_input.value = ""
                        
                        # Process message with chat pipeline
                        with ui.spinner("Processing...").classes('absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 z-50'):
                            response = chat_pipeline.process_message(user_message)
                        
                        # Display assistant response
                        with chat_box:
                            # First show the text response
                            ui.label(f"Nyx: {response['text']}").classes('self-start bg-gray-700 p-2 rounded-lg mb-2 max-w-3/4')
                            
                            # Display any generated images
                            if response.get("images") and len(response["images"]) > 0:
                                with ui.row().classes('flex-wrap gap-2 mb-2'):
                                    for idx, image_data in enumerate(response["images"]):
                                        with ui.card().classes('w-64 p-2 bg-gray-800'):
                                            # Display the image
                                            img = ui.image(image_data["url"]).classes('w-full rounded-lg cursor-pointer')
                                            img.on('click', lambda d=image_data: show_image_details(d))
                                            
                                            # Image caption with preview option
                                            short_desc = image_data["description"][:50] + ("..." if len(image_data["description"]) > 50 else "")
                                            with ui.row().classes('items-center justify-between w-full'):
                                                ui.label(short_desc).classes('text-xs italic text-gray-300 truncate max-w-[80%]')
                                                ui.button(icon='search', on_click=lambda d=image_data: show_image_details(d)).props('flat dense').classes('text-xs p-1')
                        
                        # Update mood display if provided
                        if response.get("mood"):
                            mood_display.value = response["mood"]
                            mood_label.text = "current mood"
                        
                        # Auto-scroll to bottom
                        ui.run_javascript('''
                            var element = document.querySelector('.overflow-y-auto');
                            if (element) {
                                element.scrollTop = element.scrollHeight;
                            }
                        ''')
                    
                    # Connect send button to function
                    ui.button('SEND', on_click=send_message).classes('bg-primary text-white px-8')
                    
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