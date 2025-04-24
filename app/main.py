import os
import json
import traceback
from pathlib import Path
from nicegui import app, ui
import asyncio
import logging
import yaml
from fastapi.responses import JSONResponse

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/app.log"),
        logging.StreamHandler()
    ]
)
# Reduce noise from watchfiles logs
logging.getLogger('watchfiles').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Import your components
from . import header
from . import footer
from .components import home_content
from .components import controls_content
from .components import data_content

# Import core services
from .models.database import Database
from .core.memory_system import MemorySystem
from .core.world_manager import WorldManager
from .services.chat_pipeline import ChatPipeline

# Import Qdrant initialization
from .utils.qdrant_init import initialize_qdrant
from .services.embedder import get_embedder

# Initialize database
db = Database()

# Load configuration
with open(Path(__file__).parent / 'config.yaml', 'r') as file:
    config = yaml.safe_load(file)

# Read config file
appName = config["app"]["title"]
appVersion = "Preview"  # We can add this to config later if needed
appPort = config["app"]["port"]

app.add_static_files('/assets', Path(__file__).parent / "assets")

# Initialize world state if empty
world_manager = WorldManager()
current_state = world_manager.get_current_state()
if current_state["location"] == "Default Location":
    world_manager.update_location(
        "Cyberpunk Apartment",
        "A small apartment with neon lighting and futuristic tech scattered around. The windows show a sprawling cityscape with flying vehicles.",
        "/assets/images/location.png"
    )

chat_pipeline = ChatPipeline()

# Initialize embedder and Qdrant at startup
async def _initialize_services():
    print("Starting initialization of embedding models and services...")
    
    # Initialize Qdrant collections
    try:
        qdrant_initialized = await initialize_qdrant()
        if qdrant_initialized:
            print("Qdrant collections initialized successfully")
        else:
            print("Warning: Qdrant initialization failed. Vector storage may not work properly.")
    except Exception as e:
        print(f"Error initializing Qdrant: {str(e)}")
    
    # Initialize the embedding model (CLIP)
    try:
        # Test with a simple embedding to make sure everything is loaded
        embedder = get_embedder()
        _ = embedder.embed_prompt("Test embedding initialization")
        print("Embedding models loaded successfully")
    except Exception as e:
        print(f"Error initializing embedding models: {str(e)}")

# Register startup handler
@app.on_startup
async def startup():
    await _initialize_services()

@app.post('/api/process_message')
async def process_message(request):
    data = await request.json()
    user_message = data.get('message', '')
    
    # Process the message
    response = await chat_pipeline.process_message(user_message)
    
    return response

@app.post('/api/generate_images')
async def generate_images(request):
    data = await request.json()
    response_text = data.get('response_text', '')
    
    # Generate images for the response
    images = await chat_pipeline.generate_images(response_text)
    
    return {"images": images}

@ui.page('/')
def index():
    ui.colors(
        primary='#3F2B5B',      # deep muted violet (navbar and accents)
        secondary='#A166A0',    # soft magenta (highlight touches)
        accent='#00F0FF',       # electric cyan (hover/active UI pops)
        dark='#141414',         # base dark chrome
        dark_page='#0F0F0F',    # background for pages
        positive='#53B689',     # soft green (affirmative / status)
        negative='#FF5555',     # saturated error red
        info='#31ccec',         # light neon blue
        warning='#FFC857',      # synth yellow
    )

    ui.dark_mode(True)
    ui.add_head_html("<style>" + open(Path(__file__).parent / "assets" / "css" / "global-css.css").read() + "</style>")

    with header.frame(title=appName, version=appVersion):
        with ui.header().classes(replace='row items-center').style('background-color:#3F2B5B; border-bottom: 1px solid #00F0FF;') as header_below:
            with ui.column().classes('w-full items-center'):
                with ui.tabs().props("active-color=blue-grey-14 active-bg-color=white") as tabs1:
                    with ui.row():
                        with ui.tab("tab_1", label="").style('color: black; font-family: "Rational Display", sans-serif;').props("no-caps") as tab_three:
                            ui.icon("o_home").classes('text-3xl')
                            ui.label("Home")

                        with ui.tab("tab_2", label="").style('color: black; font-family: "Rational Display", sans-serif;').props("no-caps") as tab_one:
                            ui.icon("tune").classes('text-3xl')
                            ui.label("Controls")

                        with ui.tab("tab_3", label="").style('color: black; font-family: "Rational Display", sans-serif;').props("no-caps") as tab_two:
                            ui.icon("o_analytics").classes('text-3xl')
                            ui.label("Data")

        with ui.tab_panels(tabs1, value='tab_1').classes('w-full') as tab_panel:
            with ui.tab_panel('tab_1').style('font-family: "Rational Display", sans-serif;'):
                home_content.content()
                
            with ui.tab_panel('tab_2').style('font-family: "Rational Display", sans-serif;'):
                controls_content.content()
                
            with ui.tab_panel('tab_3').style('font-family: "Rational Display", sans-serif;'):
                data_content.content()

        header_below.tailwind("pt-16")
        tab_panel.tailwind("pt-16 pl-16 pr-16")

        footer.frame(title=appName, version=appVersion)

def handle_shutdown():
    print('Shutdown has been initiated!')
    # Close database connections
    db.close()

app.on_shutdown(handle_shutdown)

# Setup custom error handling for background tasks
@app.exception_handler(Exception)
async def custom_exception_handler(request, exc):
    # Skip logging for common WebSocket disconnection errors
    error_text = str(exc)
    if any(msg in error_text for msg in [
        'Session is disconnected',
        'WebSocket is disconnected',
        'Connection closed',
        'connection already closed'
    ]):
        # Just return a response without logging for common disconnection errors
        return JSONResponse(
            content={"error": "WebSocket disconnected"},
            status_code=500
        )
    
    # Log other, potentially more serious errors
    logger.error(f"Unhandled exception: {error_text}")
    logger.error(traceback.format_exc())
    
    # Return a response to prevent connection loss
    return JSONResponse(
        content={"error": "An internal error occurred"},
        status_code=500
    )

if __name__ in {"__main__", "__mp_main__"}:
    # For dev
    ui.run(
        storage_secret="myStorageSecret", 
        title=appName, 
        port=appPort, 
        favicon='🚀',
        reconnect_timeout=120  # Increase reconnect timeout to 120 seconds
    )

    # For prod
    #ui.run(
    #    storage_secret="myStorageSecret", 
    #    title=appName, 
    #    port=appPort, 
    #    favicon='🚀',
    #    reconnect_timeout=120  # Increase reconnect timeout to 120 seconds
    #)

    # For native
    #ui.run(
    #    storage_secret="myStorageSecret", 
    #    title=appName, 
    #    port=appPort, 
    #    favicon='🚀', 
    #    reload=False, 
    #    native=True, 
    #    window_size=(1600,900),
    #    reconnect_timeout=120  # Increase reconnect timeout to 120 seconds
    #)

    # For Docker
    #ui.run(
    #    storage_secret=os.environ['STORAGE_SECRET'],
    #    reconnect_timeout=120  # Increase reconnect timeout to 120 seconds
    #)