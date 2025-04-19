import json
import httpx
from app.models.prompt_models import PromptManager, PromptType
from app.utils.config import Config
from app.utils.logger import Logger
from enum import Enum

class LLMProvider(Enum):
    LOCAL = "local"
    OPENROUTER = "openrouter"

class ImageSceneParser:
    @staticmethod
    def parse_images(response_text, current_appearance=None):
        logger = Logger()
        logger.info("Starting image parsing from Nyx response")
        logger.debug(f"Original response text: {response_text}")
        logger.debug(f"Current appearance: {current_appearance}")

        try:
            config = Config()
            parser_provider = config.get("llm", "parser_provider", "openrouter")
            parser_model = config.get("llm", "parser_model", "mistralai/mistral-large")

            logger.info(f"Using image parser: {parser_provider}/{parser_model}")

            if parser_provider == "openrouter":
                api_base = config.get("llm", "openrouter_api_base", "https://openrouter.ai/api/v1")
                api_key = config.get("llm", "openrouter_api_key", "")
                if not api_key:
                    logger.error("No OpenRouter API key found for image parser")
                    return None

                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "HTTP-Referer": config.get("llm", "http_referer", "http://localhost:8080"),
                    "X-Title": "Nyx AI Assistant - Image Parser"
                }
            else:
                api_base = config.get("llm", "local_api_base", "http://localhost:5000/v1")
                headers = {"Content-Type": "application/json"}

            # Construct system prompt
            prompt_manager = PromptManager()
            parser_data = prompt_manager.get_prompt("image_scene_parser", PromptType.IMAGE_PARSER.value)
            system_prompt = parser_data["content"] if parser_data else ImageSceneParser._default_prompt()

            logger.debug(f"System prompt for image parser:\n{system_prompt}")

            # Parse the input JSON if it's a JSON string
            try:
                input_data = json.loads(response_text)
                if isinstance(input_data, dict) and "images" in input_data:
                    # Extract sequence information
                    sequences = [img.get("sequence", i+1) for i, img in enumerate(input_data["images"])]
                    # Join all image contents with context
                    image_text = []
                    if "mood" in input_data:
                        image_text.append(f"Current mood: {input_data['mood']}")
                    if "appearance" in input_data:
                        image_text.append(f"Current appearance: {input_data['appearance']}")
                    if "location" in input_data:
                        image_text.append(f"Current location: {input_data['location']}")
                    image_text.extend([f"Image {seq}: {img['content']}" for seq, img in zip(sequences, input_data["images"])])
                    image_text = "\n".join(image_text)
                else:
                    image_text = response_text
            except json.JSONDecodeError:
                image_text = response_text

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"{image_text}"}
            ]

            logger.debug(f"Full messages for image parser:\n{json.dumps(messages, indent=2)}")

            endpoint = f"{api_base}/chat/completions"
            payload = {
                "model": parser_model,
                "messages": messages,
                "temperature": 0.2,
                "max_tokens": 1024,
                "response_format": {"type": "json_object"}
            }

            logger.debug(f"Image parser request to {endpoint}: {json.dumps(payload, indent=2)}")

            response = httpx.post(endpoint, json=payload, headers=headers, timeout=30)
            response.raise_for_status()

            response_data = response.json()
            parsed_content = response_data["choices"][0]["message"]["content"]

            try:
                result = json.loads(parsed_content)
                if not isinstance(result, dict) or "images" not in result:
                    logger.error(f"Invalid response format: {result}")
                    return None
                
                images = result["images"]
                if not isinstance(images, list):
                    logger.error(f"Images is not a list: {images}")
                    return None
                
                # If we have sequence information, preserve it
                if isinstance(input_data, dict) and "images" in input_data:
                    sequences = [img.get("sequence", i+1) for i, img in enumerate(input_data["images"])]
                    images = [{"content": img, "sequence": seq} for img, seq in zip(images, sequences)]
                
                logger.info("Successfully parsed image scenes")
                return images
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {str(e)}")
                return None

        except Exception as e:
            logger.error(f"Error in image scene parsing: {str(e)}", exc_info=True)
            return None

    @staticmethod
    def _default_prompt():
        return """You are a visual parser for AI-generated character responses.

Your task is to extract 1–5 individual image prompts from a dialogue response. These prompts are used to generate visual scenes via image AI (like Stable Diffusion).

You will receive:
1. Nyx's current appearance (as plain text)
2. A full response from her (natural language only)

---

🎯 INSTRUCTIONS:

- Extract visual moments: If the response contains a sequence (e.g., "unzips suit, steps forward, smiles"), split into individual image scenes.
- Each image prompt must describe a **single moment** only.
- ALWAYS include Nyx's current appearance in your descriptions, but describe it naturally (e.g., "a woman with cybernetic enhancements" instead of "Nyx").
- For appearance changes, describe both the change and the current state (e.g., "unzips her bodysuit halfway, revealing the glowing circuits beneath").
- Include details like: pose, outfit, lighting, environment, mood, actions.
- Omit story transitions ("then", "next", etc.). Focus on **visual freeze-frames**.
- Do not censor erotic or suggestive content. Nyx and user are adults.
- Format output as a clean JSON list of image descriptions.

Return only the `images` array in valid JSON. No commentary.
"""