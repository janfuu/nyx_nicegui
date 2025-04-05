from nicegui import ui
import httpx
import asyncio
import redis
import threading
from datetime import datetime

# --- Configuration ---
backend_url = 'http://localhost:8888'
redis_host = 'localhost'
redis_port = 6379

# --- Shared state ---
state = {
    'mood': 'neutral',
    'portrait_image_url': 'static/portrait.jpg',
    'location_image_url': 'static/location.png',
    'location_desc': 'cyberpunk apartment interior at night... synthwave color palette',
    'monologue': "It's... unusual to be addressed so familiarly...",
    'chat_history': [],
    'needs_refresh': {
        'chat': False
    }
}

# --- Redis Listener Thread ---
def redis_listener_thread():
    r = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
    pubsub = r.pubsub()
    pubsub.subscribe('nyx:mood', 'nyx:image', 'nyx:location', 'nyx:monologue')
    for message in pubsub.listen():
        if message['type'] != 'message':
            continue
        channel = message['channel']
        data = message['data']
        if channel == 'nyx:image':
            state['portrait_image_url'] = data
        elif channel == 'nyx:location':
            state['location_image_url'] = data
        elif channel == 'nyx:mood':
            state['mood'] = data
        elif channel == 'nyx:monologue':
            state['monologue'] = data

# --- Start Redis Listener ---
def start_redis_listener():
    threading.Thread(target=redis_listener_thread, daemon=True).start()

# --- Helper ---
def get_time():
    return datetime.now().strftime('%H:%M')

# --- Send message ---
def send_message(msg, input_box):
    if not msg.strip():
        return
    input_box.value = ''
    state['chat_history'].append(('You', msg))
    state['needs_refresh']['chat'] = True

    async def talk_to_backend():
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(f'{backend_url}/chat', json={'user_input': msg})
                nyx_reply = resp.json()['response']
        except Exception as e:
            nyx_reply = f"Error: {e}"
        state['chat_history'].append(('Nyx', nyx_reply))
        state['needs_refresh']['chat'] = True

    asyncio.create_task(talk_to_backend())

# --- UI ---
ui.colors(primary='#6366f1', secondary='#ec4899', dark=True)
start_redis_listener()

with ui.column().classes('w-full h-screen bg-[#0f0f0f] text-white'):
    with ui.row().classes('w-full h-full flex justify-between'):

        # --- Left Panel ---
        with ui.column().classes('w-1/4 p-4 gap-4'):
            ui.image(state['portrait_image_url']).classes('rounded-xl h-72 object-cover')
            ui.textarea(value=state['monologue']).props('readonly auto-grow')\
                .classes('bg-[#1a1a1a] rounded p-2 text-sm')

            ui.label('Error').classes('text-red-500')
            with ui.column().classes('gap-1'):
                ui.button('CHECK TABLE').classes('text-xs w-full')
                ui.button('INIT MEMORY').classes('text-xs w-full')
                ui.button('DEBUG MEMORIES').classes('text-xs w-full')
                ui.button('FORCE MEMORY').classes('text-xs w-full')

        # --- Center Panel ---
        with ui.column().classes('w-2/4 p-4 gap-2'):
            chat_box = ui.column().classes('h-[500px] overflow-y-auto bg-[#1a1a1a] p-4 rounded')

            @ui.refreshable
            def render_chat():
                chat_box.clear()
                for speaker, msg in state['chat_history']:
                    name_color = 'text-secondary' if speaker == 'Nyx' else 'text-primary'
                    with chat_box:
                        ui.label(f"{speaker} ({get_time()}):").classes(f'font-bold text-sm {name_color}')
                        ui.label(msg).classes('text-sm mb-3')

            ui.timer(0.5, lambda: (render_chat.refresh() if state['needs_refresh']['chat'] else None))

            with ui.row().classes('gap-2 mt-auto'):
                msg_input = ui.input(placeholder='Type a message...').classes('w-full bg-[#1f1f1f] text-white')
                ui.button('SEND', on_click=lambda: send_message(msg_input.value, msg_input))\
                    .classes('bg-primary text-white')

        # --- Right Panel ---
        with ui.column().classes('w-1/4 p-4 gap-4'):
            ui.image(state['location_image_url']).classes('rounded-xl h-72 object-cover')
            ui.label(state['location_desc']).classes('text-xs text-gray-400')

ui.run(title='Nyx Chat')
