import asyncio
import os
from dotenv import load_dotenv
from app.core.image_generator import ImageGenerator
from app.core.response_parser import ResponseParser
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
    test_prompt = "A cyberpunk city street at night, neon lights, rain, futuristic buildings, digital art style"
    print(f"\nGenerating image with prompt: {test_prompt}")
    
    try:
        image_url = await image_generator.generate(test_prompt)
        if image_url:
            print(f"Success! Image generated at: {image_url}")
        else:
            print("Failed to generate image")
    except Exception as e:
        logger.error(f"Error in image generation: {str(e)}", exc_info=True)
        print(f"Error: {str(e)}")

async def test_response_parser():
    """Test the response parser with image tags"""
    print("\n=== Testing Response Parser ===")
    
    # Test response with image tags
    test_response = """
    Hello! Let me show you something interesting.
    
    <image>A futuristic cityscape at sunset, with flying cars and holographic advertisements, cyberpunk style, digital art, high detail</image>
    
    <thought>I wonder if they'll like this view of the future</thought>
    
    <mood>excited</mood>
    
    What do you think about this vision of the future?
    """
    
    print(f"\nParsing response with image tags:\n{test_response}")
    
    parsed_result = ResponseParser.parse_response(test_response)
    print("\nParsed result:")
    print(f"Main text: {parsed_result.get('main_text', '')}")
    print(f"Thoughts: {parsed_result.get('thoughts', [])}")
    print(f"Images: {parsed_result.get('images', [])}")
    print(f"Mood: {parsed_result.get('mood', '')}")

async def test_combined():
    """Test both components together"""
    print("\n=== Testing Combined Functionality ===")
    
    # First parse a response with image tags
    test_response = """
    Let me show you something beautiful.
    
    <image>A serene mountain landscape at dawn, misty valleys, golden sunlight, digital art style, high detail, trending on artstation</image>
    
    <thought>Nature's beauty always brings peace</thought>
    """
    
    print("\nParsing response with image tags...")
    parsed_result = ResponseParser.parse_response(test_response)
    
    if parsed_result.get('images'):
        print("\nGenerating image from parsed prompt...")
        image_generator = ImageGenerator()
        image_url = await image_generator.generate(parsed_result['images'][0])
        if image_url:
            print(f"Success! Image generated at: {image_url}")
        else:
            print("Failed to generate image")
    else:
        print("No image prompts found in parsed response")

async def main():
    """Run all tests"""
    await test_image_generator()
    await test_response_parser()
    await test_combined()

if __name__ == "__main__":
    asyncio.run(main()) 