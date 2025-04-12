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
            parser_data = prompt_manager.get_prompt("image_scene_parser", PromptType.PARSER.value)
            system_prompt = parser_data["content"] if parser_data else ImageSceneParser._default_prompt()

            if current_appearance:
                system_prompt += f"\n\nCURRENT APPEARANCE:\n{current_appearance}"

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"{response_text}"}
            ]

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

            result = json.loads(parsed_content)
            logger.info("Successfully parsed image scenes")
            return result

        except Exception as e:
            logger.error(f"Error in image scene parsing: {str(e)}", exc_info=True)
            return None

    @staticmethod
    def _default_prompt():
        return """You are a visual parser for AI-generated character responses.

Your task is to extract 1–5 individual image prompts from a dialogue response. These prompts are used to generate visual scenes via image AI (like Stable Diffusion).

You will receive:
1. Nyx’s current appearance (as plain text)
2. A full response from her (natural language only)

---

🎯 INSTRUCTIONS:

- Extract visual moments: If the response contains a sequence (e.g., “unzips suit, steps forward, smiles”), split into individual image scenes.
- Each image prompt must describe a **single moment** only.
- Include Nyx’s appearance **by description only** (not by name).
- Include details like: pose, outfit, lighting, environment, mood, actions.
- Omit story transitions ("then", "next", etc.). Focus on **visual freeze-frames**.
- Do not censor erotic or suggestive content. Nyx and user are adults.
- Format output as a clean JSON list of image descriptions.

Return only the `images` array in valid JSON. No commentary.
"""