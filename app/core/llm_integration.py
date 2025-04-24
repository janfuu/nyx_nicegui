"""
LLM Integration Service
======================

This module provides the core interface for interacting with the OpenRouter Language Model (LLM) provider.
It handles:
1. Communication with OpenRouter API
2. Message formatting and prompt building
3. Response streaming and error handling
4. Configuration management

The service provides a consistent interface for the rest of the application to interact with the language model.
"""

import httpx
import json
import time
from app.utils.config import Config
from app.utils.logger import Logger

class LLMIntegration:
    """
    Main interface for interacting with the OpenRouter language model.
    
    This class provides a unified interface for:
    1. Sending requests to OpenRouter
    2. Handling streaming and non-streaming responses
    3. Managing configuration
    4. Error handling and logging
    
    It ensures proper communication with the OpenRouter service while maintaining
    consistent behavior for the rest of the application.
    """
    def __init__(self):
        self.config = Config()
        self.logger = Logger()
        
        # --- Default Configuration ---
        self.default_model = self.config.get("llm", "model", "gpt-4")
        self.max_messages = int(self.config.get("llm", "max_messages", 20))
        self.timeout = int(self.config.get("llm", "timeout", 60))
        self.use_streaming = self.config.get("llm", "use_streaming", False)

    def _get_api_base(self):
        """
        Get the OpenRouter API base URL.
        """
        return self.config.get("llm", "openrouter_api_base", "https://openrouter.ai/api/v1")

    def _get_headers(self):
        """
        Get the OpenRouter HTTP headers.
        """
        openrouter_api_key = self.config.get("llm", "openrouter_api_key", "")
        return {
            "Authorization": f"Bearer {openrouter_api_key}",
            "HTTP-Referer": self.config.get("llm", "http_referer", "http://localhost:8080"),
            "X-Title": "Nyx AI Assistant"
        }

    def _build_payload(self, messages=None, model=None):
        """
        Build the OpenRouter request payload.
        """
        model = model or self.default_model
        return {
            "model": model,
            "messages": messages,
            "temperature": self.config.get("llm", "temperature", 0.8),
            "max_tokens": self.config.get("llm", "max_tokens", 512),
            "stop": ["<end_of_turn>"]
        }

    async def generate_response(self, system_prompt, user_message, conversation_history=None, model=None):
        """
        Generate a response from the OpenRouter LLM.
        
        This is the main entry point for generating responses. It:
        1. Validates OpenRouter configuration and API key
        2. Handles both streaming and non-streaming responses
        3. Logs the complete conversation for debugging
        4. Manages errors and provides fallback responses
        """
        if conversation_history is None:
            conversation_history = []
            
        model = model or self.default_model
        
        # Log input parameters
        self.logger.debug(f"Generating response with model={model}")
        
        # Check if API key is available
        api_key = self.config.get("llm", "openrouter_api_key", "")
        if not api_key:
            error_msg = "No OpenRouter API key found. Please set OPENROUTER_API_KEY environment variable or in config.json"
            self.logger.error(error_msg)
            return f"I'm having trouble connecting to my thoughts right now. {error_msg}"

        try:
            response = await self._generate_openrouter_response(
                system_prompt, user_message, conversation_history, model
            )
                
            # Log the complete conversation
            self.logger.log_conversation(
                system_prompt=system_prompt,
                user_message=user_message,
                conversation_history=conversation_history,
                llm_response=response,
                model=model
            )
            
            return response
        except Exception as e:
            self.logger.error(f"Error in generate_response: {str(e)}")
            return self._handle_error(e)

    async def _generate_openrouter_response(self, system_prompt, user_message, conversation_history, model):
        """
        Generate a response using the OpenRouter API.
        
        This method handles the specific requirements of the OpenRouter API:
        1. Formats messages in the chat completion format
        2. Handles streaming and non-streaming responses
        3. Manages API-specific error cases
        4. Logs request and response details
        """
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(conversation_history[-self.max_messages:])
        messages.append({"role": "user", "content": user_message})

        payload = self._build_payload(messages=messages, model=model)
        api_base = self._get_api_base()
        headers = self._get_headers()
        endpoint = f"{api_base}/chat/completions"
        
        # Log API request details
        self.logger.debug(f"OpenRouter request to {endpoint}")
        self.logger.debug(f"Payload: {json.dumps(payload, indent=2)}")

        start_time = time.time()
        
        if self.use_streaming:
            response = await self._handle_streaming_response(endpoint, {**payload, "stream": True}, headers)
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

    async def _handle_streaming_response(self, endpoint, payload, headers):
        """
        Handle streaming responses from OpenRouter.
        
        This method manages the streaming response process:
        1. Establishes a streaming connection to the API
        2. Processes incoming chunks in real-time
        3. Handles response format
        4. Manages connection errors and timeouts
        """
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
                            content = chunk["choices"][0].get("delta", {}).get("content", "")
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