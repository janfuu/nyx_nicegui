import asyncio
import os
from dotenv import load_dotenv
from app.core.image_generator import ImageGenerator
from app.core.response_parser import ResponseParser
from app.core.image_scene_parser import ImageSceneParser
from app.models.prompt_models import PromptManager, PromptType
from app.core.memory_system import MemorySystem
from app.utils.logger import Logger

# Load environment variables first
load_dotenv()

# Initialize logger
logger = Logger()

async def test_image_generator():
    """Test the image generator directly"""
    print("\n=== Testing Image Generator ===")
    
    # Verify Runware API key is loaded
    runware_key = os.getenv('RUNWARE_API_KEY')
    if not runware_key:
        print("Error: RUNWARE_API_KEY not found in environment")
        return
        
    image_generator = ImageGenerator()
    
    # Test with a simple prompt
    test_prompt = {
        "prompt": "A cyberpunk city street at night, neon lights, rain, futuristic buildings, digital art style",
        "orientation": "landscape"
    }
    print(f"\nGenerating image with prompt: {test_prompt}")
    
    try:
        image_url = await image_generator.generate([test_prompt])
        if image_url:
            print(f"Success! Image generated at: {image_url}")
        else:
            print("Failed to generate image")
    except Exception as e:
        logger.error(f"Error in image generation: {str(e)}", exc_info=True)
        print(f"Error: {str(e)}")

async def test_response_parser():
    """Test the response parser with mood and thought inference"""
    print("\n=== Testing Response Parser ===")
    
    # Test response with implicit mood and thoughts
    test_response = """
    Hello! I'm feeling quite excited about this new development. 
    *smiles warmly* The future looks bright, doesn't it?
    
    <thought>I wonder if they'll appreciate this positive outlook</thought>
    
    What do you think about this vision of the future?
    """
    
    print(f"\nParsing response with implicit mood and thoughts:\n{test_response}")
    
    parsed_result = ResponseParser.parse_response(test_response)
    print("\nParsed result:")
    print(f"Main text: {parsed_result.get('main_text', '')}")
    print(f"Thoughts: {parsed_result.get('thoughts', [])}")
    print(f"Mood: {parsed_result.get('mood', '')}")

async def test_image_scene_parser():
    """Test the image scene parser with natural language"""
    print("\n=== Testing Image Scene Parser ===")
    
    # Test response with visual descriptions
    test_response = """
    I'm standing by the window, looking out at the neon-lit cityscape. The rain is falling gently, 
    creating a beautiful reflection of the lights on the wet streets. I turn to you with a smile, 
    my cybernetic circuits glowing softly in the dim light.
    """
    
    print(f"\nParsing response for visual scenes:\n{test_response}")
    
    # Get current appearance for context
    memory_system = MemorySystem()
    current_appearance = memory_system.get_recent_appearances(1)
    current_appearance_text = current_appearance[0]["description"] if current_appearance else None
    
    parsed_scenes = await ImageSceneParser.parse_images(test_response, current_appearance_text)
    print("\nParsed scenes:")
    if parsed_scenes:
        for i, scene in enumerate(parsed_scenes):
            print(f"\nScene {i+1}:")
            print(scene)
    else:
        print("No visual scenes found")

async def test_combined():
    """Test both components together with on-demand image generation"""
    print("\n=== Testing Combined Functionality ===")
    
    # First parse a response with visual descriptions
    test_response = """
    I'm standing by the window, looking out at the neon-lit cityscape. The rain is falling gently, 
    creating a beautiful reflection of the lights on the wet streets. I turn to you with a smile, 
    my cybernetic circuits glowing softly in the dim light.
    """
    
    print("\nParsing response for visual scenes...")
    
    # Get current appearance for context
    memory_system = MemorySystem()
    current_appearance = memory_system.get_recent_appearances(1)
    current_appearance_text = current_appearance[0]["description"] if current_appearance else None
    
    parsed_scenes = await ImageSceneParser.parse_images(test_response, current_appearance_text)
    
    if parsed_scenes:
        print("\nGenerating images from parsed scenes...")
        image_generator = ImageGenerator()
        
        for i, scene in enumerate(parsed_scenes):
            print(f"\nGenerating image {i+1} from scene:")
            print(scene)
            
            # Convert scene to proper format if needed
            if isinstance(scene, dict) and 'prompt' in scene:
                # Scene is already in the right format
                scene_data = scene
            else:
                # Convert to standardized format
                scene_data = {
                    "prompt": scene if isinstance(scene, str) else str(scene),
                    "orientation": "portrait"  # Default orientation
                }
                
            image_url = await image_generator.generate([scene_data])
            if image_url:
                print(f"Success! Image generated at: {image_url}")
            else:
                print("Failed to generate image")
    else:
        print("No visual scenes found in parsed response")

async def main():
    """Run all tests"""
    # Reset parser prompts to latest version
    prompt_manager = PromptManager()
    prompt_manager.reset_to_default("response_parser", PromptType.RESPONSE_PARSER.value)
    prompt_manager.reset_to_default("image_scene_parser", PromptType.IMAGE_PARSER.value)
    
    await test_image_generator()
    await test_response_parser()
    await test_image_scene_parser()
    await test_combined()

if __name__ == "__main__":
    asyncio.run(main()) 