# app/core/llm_integration.py

import httpx
import json
import time
from enum import Enum
from app.utils.config import Config
from app.core.prompt_builder import PromptBuilder
from app.utils.logger import Logger

class LLMProvider(Enum):
    LOCAL = "local"
    OPENROUTER = "openrouter"
    RUNWARE = "runware"

class LLMIntegration:
    def __init__(self):
        self.config = Config()
        self.logger = Logger()
        
        # --- Default Configuration ---
        self.default_provider = LLMProvider(self.config.get("llm", "provider", "local"))
        self.default_model = self.config.get("llm", "model", "gpt-4")
        self.max_messages = int(self.config.get("llm", "max_messages", 20))
        self.timeout = int(self.config.get("llm", "timeout", 60))
        self.use_streaming = self.config.get("llm", "use_streaming", False)
        self.api_key = self.config.get("llm", "api_key", "")

        # --- System Identity ---
        self.default_persona = (
            "You are Nyx, a curious, emotionally nuanced AI companion. "
            "You remember past conversations, have moods, and sometimes secrets. "
            "Speak naturally and stay in character. Avoid disclaimers."
        )

        self.nyx_appearance = (
            "You have a distinctive appearance: a futuristic woman with shimmering silver skin, "
            "chrome facial accents, dark hair. "
            "You may be visualized in images when referenced as 'me', 'myself', or similar."
        )

    def _get_api_base(self, provider=None):
        provider = provider or self.default_provider
        if provider == LLMProvider.OPENROUTER:
            return self.config.get("llm", "openrouter_api_base", "https://openrouter.ai/api/v1")
        return self.config.get("llm", "local_api_base", "http://localhost:5000/v1")

    def _get_headers(self, provider=None):
        provider = provider or self.default_provider
        
        if provider == LLMProvider.OPENROUTER:
            openrouter_api_key = self.config.get("llm", "openrouter_api_key", "")
            return {
                "Authorization": f"Bearer {openrouter_api_key}",
                "HTTP-Referer": self.config.get("llm", "http_referer", "http://localhost:8080"),
                "X-Title": "Nyx AI Assistant"
            }
        else:  # LOCAL or any other provider
            return {
                "Content-Type": "application/json"
            }

    def _build_payload(self, messages=None, prompt=None, provider=None, model=None):
        provider = provider or self.default_provider
        model = model or self.default_model
        
        if provider == LLMProvider.OPENROUTER:
            return {
                "model": model,
                "messages": messages,
                "temperature": self.config.get("llm", "temperature", 0.8),
                "max_tokens": self.config.get("llm", "max_tokens", 512),
            }
        else:
            return {
                "model": model,
                "prompt": prompt,
                "max_tokens": self.config.get("llm", "max_tokens", 512),
                "max_new_tokens": self.config.get("llm", "max_new_tokens", 512),
                "truncation_length": self.config.get("llm", "truncation_length", 2048),
                "temperature": self.config.get("llm", "temperature", 0.8),
                "stop": ["<end_of_turn>"]
            }

    def build_system_message(self, mood=None, relevant_memories=None, current_appearance=None):
        """Build the system message with mood, memories and appearance"""
        system_prompt = PromptBuilder.build_system_message(
            relevant_memories=relevant_memories,
            current_mood=mood,
            current_appearance=current_appearance
        )
        
        return {
            "role": "system",
            "content": system_prompt
        }

    async def generate_response(self, system_prompt, user_message, conversation_history=None, 
                          provider=None, model=None):
        """
        Generate a response from the LLM
        
        Args:
            system_prompt: The system prompt to guide the AI
            user_message: The user's message
            conversation_history: List of previous messages
            provider: Override the default provider (LOCAL or OPENROUTER)
            model: Override the default model
        """
        if conversation_history is None:
            conversation_history = []
            
        provider = LLMProvider(provider) if provider else self.default_provider
        model = model or self.default_model
        
        # Log input parameters
        self.logger.debug(f"Generating response with provider={provider.value}, model={model}")
        
        # Check if API key is available for the selected provider
        if provider == LLMProvider.OPENROUTER:
            api_key = self.config.get("llm", "openrouter_api_key", "")
            if not api_key:
                error_msg = "No OpenRouter API key found. Please set OPENROUTER_API_KEY environment variable or in config.json"
                self.logger.error(error_msg)
                return f"I'm having trouble connecting to my thoughts right now. {error_msg}"
        elif provider == LLMProvider.RUNWARE:
            api_key = self.config.get("llm", "runware_api_key", "")
            if not api_key:
                error_msg = "No Runware API key found. Please set RUNWARE_API_KEY environment variable or in config.json"
                self.logger.error(error_msg)
                return f"I'm having trouble connecting to my thoughts right now. {error_msg}"

        try:
            response = ""
            if provider == LLMProvider.OPENROUTER:
                response = await self._generate_openrouter_response(
                    system_prompt, user_message, conversation_history, model
                )
            else:
                response = await self._generate_local_response(
                    system_prompt, user_message, conversation_history, model
                )
                
            # Log the complete conversation
            self.logger.log_conversation(
                system_prompt=system_prompt,
                user_message=user_message,
                conversation_history=conversation_history,
                llm_response=response,
                provider=provider.value,
                model=model
            )
            
            return response
        except Exception as e:
            self.logger.error(f"Error in generate_response: {str(e)}")
            return self._handle_error(e)

    async def _generate_openrouter_response(self, system_prompt, user_message, conversation_history, model):
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(conversation_history[-self.max_messages:])
        messages.append({"role": "user", "content": user_message})

        payload = self._build_payload(
            messages=messages, 
            provider=LLMProvider.OPENROUTER, 
            model=model
        )
        api_base = self._get_api_base(LLMProvider.OPENROUTER)
        headers = self._get_headers(LLMProvider.OPENROUTER)
        endpoint = f"{api_base}/chat/completions"
        
        # Log API request details
        self.logger.debug(f"OpenRouter request to {endpoint}")
        self.logger.debug(f"Payload: {json.dumps(payload, indent=2)}")

        start_time = time.time()
        
        if self.use_streaming:
            response = await self._handle_streaming_response(endpoint, {**payload, "stream": True}, True, headers)
        else:
            async with httpx.AsyncClient() as client:
                api_response = await client.post(endpoint, json=payload, headers=headers, timeout=self.timeout)
                api_response.raise_for_status()
                
                # Log raw API response
                self.logger.debug(f"OpenRouter response: {api_response.text}")
                
                response = api_response.json()["choices"][0]["message"]["content"].strip()
        
        end_time = time.time()
        self.logger.info(f"OpenRouter request completed in {end_time - start_time:.2f} seconds")
        
        return response

    async def _generate_local_response(self, system_prompt, user_message, conversation_history, model):
        context = [{"role": "system", "content": system_prompt}]
        context.extend(conversation_history[-self.max_messages:])
        context.append({"role": "user", "content": user_message})
        
        prompt = PromptBuilder.build_prompt(context)
        payload = self._build_payload(
            prompt=prompt, 
            provider=LLMProvider.LOCAL, 
            model=model
        )
        api_base = self._get_api_base(LLMProvider.LOCAL)
        headers = self._get_headers(LLMProvider.LOCAL)
        endpoint = f"{api_base}/completions"
        
        # Log the complete prompt that will be sent
        self.logger.debug(f"Local LLM request to {endpoint}")
        self.logger.debug(f"Full prompt:\n{prompt}")

        start_time = time.time()
        
        if self.use_streaming:
            response = await self._handle_streaming_response(endpoint, {**payload, "stream": True}, False, headers)
        else:
            async with httpx.AsyncClient() as client:
                api_response = await client.post(endpoint, json=payload, headers=headers, timeout=self.timeout)
                api_response.raise_for_status()
                
                # Log raw API response
                self.logger.debug(f"Local LLM response: {api_response.text}")
                
                response = api_response.json()["choices"][0]["text"].strip()
        
        end_time = time.time()
        self.logger.info(f"Local LLM request completed in {end_time - start_time:.2f} seconds")
        
        return response

    async def _handle_streaming_response(self, endpoint, payload, is_openrouter, headers):
        reply = ""
        async with httpx.AsyncClient() as client:
            async with client.stream('POST', endpoint, json=payload, headers=headers, timeout=self.timeout) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        if line.startswith("data: "):
                            json_str = line[6:]
                            if json_str == "[DONE]":
                                break
                            chunk = json.loads(json_str)
                            if is_openrouter:
                                content = chunk["choices"][0].get("delta", {}).get("content", "")
                            else:
                                content = chunk["choices"][0].get("text", "")
                            reply += content
                    except Exception as e:
                        print(f"Error parsing stream chunk: {e}")
        return reply

    def _handle_error(self, e):
        error_msg = str(e)
        self.logger.error(f"LLM API error: {error_msg}")
        
        detailed_error = error_msg
        if hasattr(e, 'response') and e.response:
            try:
                error_content = e.response.json()
                detailed_error = json.dumps(error_content, indent=2)
                self.logger.error(f"Detailed API error: {detailed_error}")
            except:
                detailed_error = e.response.text if e.response.text else error_msg
                self.logger.error(f"API error text: {detailed_error}")
        
        return f"I'm having trouble connecting to my thoughts right now. {detailed_error}"