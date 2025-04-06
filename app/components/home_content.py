from nicegui import ui, app

def content() -> None:
    with ui.row().classes('w-full gap-4 flex-nowrap'):
        # Left Card
        with ui.card().classes('flex-1'):
            with ui.column().classes('gap-4 w-full'):
                ui.image('assets/images/portrait.jpg').classes('w-full rounded-xl')
                ui.textarea(value="It's... unusual to be addressed so familiarly...").props('readonly auto-grow')\
                    .classes('bg-[#1a1a1a] rounded p-2 text-sm w-full')
                ui.label('mood').classes('text-blue-500')

        # Center Card
        with ui.card().classes('flex-2 w-[800px]'):  # Make center card wider
            with ui.column().classes('h-full w-full gap-4'):
                chat_box = ui.column().classes('h-[600px] overflow-y-auto bg-[#1a1a1a] p-6 rounded w-full')

                @ui.refreshable
                def render_chat():
                    chat_box.clear()
                    # Chat history will be populated from main.py

                with ui.row().classes('gap-4 mt-auto w-full'):
                    msg_input = ui.input(placeholder='Type a message...').classes('flex-1 bg-[#1f1f1f] text-white')
                    ui.button('SEND', on_click=lambda: None).classes('bg-primary text-white px-8')

        # Right Card
        with ui.card().classes('flex-1'):
            with ui.column().classes('gap-4 w-full'):
                ui.image('assets/images/location.png').classes('w-full rounded-xl')
                ui.label('cyberpunk apartment interior at night... synthwave color palette').classes('text-xs text-gray-400')