# app/core/llm_integration.py

import httpx
import json
import time
from enum import Enum
from app.utils.config import Config
from app.core.prompt_builder import PromptBuilder

class LLMProvider(Enum):
    LOCAL = "local"
    OPENROUTER = "openrouter"
    RUNWARE = "runware"

class LLMIntegration:
    def __init__(self):
        self.config = Config()
        
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

    def build_system_message(self, mood=None, relevant_memories=None):
        """Build the system message with mood and memories"""
        system_prompt = PromptBuilder.build_system_message(
            relevant_memories=relevant_memories,
            current_mood=mood
        )
        
        return {
            "role": "system",
            "content": system_prompt
        }

    def generate_response(self, system_prompt, user_message, conversation_history=None, 
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
            
        provider = provider or self.default_provider
        model = model or self.default_model

        try:
            if provider == LLMProvider.OPENROUTER:
                return self._generate_openrouter_response(
                    system_prompt, user_message, conversation_history, model
                )
            else:
                return self._generate_local_response(
                    system_prompt, user_message, conversation_history, model
                )
        except Exception as e:
            return self._handle_error(e)

    def _generate_openrouter_response(self, system_prompt, user_message, conversation_history, model):
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

        if self.use_streaming:
            return self._handle_streaming_response(endpoint, {**payload, "stream": True}, True, headers)
        
        response = httpx.post(endpoint, json=payload, headers=headers, timeout=self.timeout)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()

    def _generate_local_response(self, system_prompt, user_message, conversation_history, model):
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

        if self.use_streaming:
            return self._handle_streaming_response(endpoint, {**payload, "stream": True}, False, headers)

        response = httpx.post(endpoint, json=payload, headers=headers, timeout=self.timeout)
        response.raise_for_status()
        return response.json()["choices"][0]["text"].strip()

    def _handle_streaming_response(self, endpoint, payload, is_openrouter, headers):
        reply = ""
        response = httpx.post(endpoint, json=payload, headers=headers, timeout=self.timeout)
        response.raise_for_status()

        for line in response.iter_lines():
            if not line.strip():
                continue
            try:
                if line.startswith(b"data: "):
                    json_str = line[6:].decode("utf-8")
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
        print(f"Error calling LLM API: {error_msg}")
        
        detailed_error = error_msg
        if hasattr(e, 'response') and e.response:
            try:
                error_content = e.response.json()
                detailed_error = json.dumps(error_content, indent=2)
            except:
                detailed_error = e.response.text if e.response.text else error_msg
        
        return f"I'm having trouble connecting to my thoughts right now. {detailed_error}"