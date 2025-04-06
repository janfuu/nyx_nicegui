# app/core/llm_integration.py

import httpx
import json
import time
from app.utils.config import Config
from app.core.prompt_builder import PromptBuilder

class LLMIntegration:
    def __init__(self):
        self.config = Config()
        
        # --- Configuration ---
        self.api_base = self.config.get("llm", "api_base", "http://localhost:5000/v1")
        self.model = self.config.get("llm", "model", "gpt-4")
        self.max_messages = int(self.config.get("llm", "max_messages", 20))
        self.timeout = int(self.config.get("llm", "timeout", 60))
        self.use_streaming = self.config.get("llm", "use_streaming", False)
        
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
    
    def build_system_message(self, mood=None, relevant_memories=None):
        """Build the system message with mood and memories"""
        parts = [self.default_persona, self.nyx_appearance]

        if mood:
            parts.append(f"\nCURRENT MOOD: You are currently feeling {mood}.")

        if relevant_memories:
            memory_lines = ["\nRELEVANT MEMORIES:"]
            for memory in relevant_memories:
                memory_lines.append(f"- {memory['type'].upper()}: {memory['value']}")
            parts.append("\n".join(memory_lines))

        return {
            "role": "system",
            "content": "\n\n".join(parts)
        }
    
    def generate_response(self, system_prompt, user_message, conversation_history=None):
        """
        Generate a response from the LLM
        
        Args:
            system_prompt: The system prompt as a string
            user_message: The current user message
            conversation_history: List of previous messages as {"role": role, "content": content}
            
        Returns:
            The LLM's response as a string
        """
        if conversation_history is None:
            conversation_history = []
            
        # Build context for the prompt
        context = []
        
        # Add system message
        context.append({"role": "system", "content": system_prompt})
        
        # Add conversation history
        if conversation_history:  # Only slice if we have history
            for msg in conversation_history[-self.max_messages:]:
                context.append(msg)
            
        # Add current user message if not already in history
        if not (conversation_history and conversation_history[-1]["role"] == "user" and 
                conversation_history[-1]["content"] == user_message):
            context.append({"role": "user", "content": user_message})
        
        # Build the full prompt using the prompt builder
        prompt = PromptBuilder.build_prompt(context)
        
        # For debugging
        print("----- Rendered Prompt Start -----")
        print(prompt)
        print("------ Rendered Prompt End ------")
        
        # Setup the request payload
        payload = {
            "model": self.model,
            "prompt": prompt,
            "max_tokens": self.config.get("llm", "max_tokens", 512),
            "max_new_tokens": self.config.get("llm", "max_new_tokens", 512),
            "truncation_length": self.config.get("llm", "truncation_length", 2048),
            "temperature": self.config.get("llm", "temperature", 0.8),
            "stop": ["<end_of_turn>"]
        }
        
        try:
            start_time = time.time()
            print(f"Starting LLM request at {start_time}")
            
            if self.use_streaming:
                reply = ""
                # Make sure we include all parameters even with streaming
                stream_payload = payload.copy()
                stream_payload["stream"] = True
                
                response = httpx.post(
                    f"{self.api_base}/completions",
                    json=stream_payload,
                    timeout=self.timeout,
                )
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
                            if chunk["choices"][0].get("text"):
                                reply += chunk["choices"][0]["text"]
                    except Exception as e:
                        print(f"Error parsing stream chunk: {e}")
            else:
                response = httpx.post(
                    f"{self.api_base}/completions",
                    json=payload,
                    timeout=self.timeout
                )
                response.raise_for_status()
                reply = response.json()["choices"][0]["text"].strip()
            
            end_time = time.time()
            print(f"LLM request completed in {end_time - start_time:.2f} seconds")
            
            return reply
            
        except Exception as e:
            error_msg = str(e)
            print(f"Error calling LLM API: {error_msg}")
            
            # Try to extract more detail from the error
            detailed_error = error_msg
            if hasattr(e, 'response') and e.response:
                try:
                    error_content = e.response.json()
                    detailed_error = json.dumps(error_content, indent=2)
                except:
                    detailed_error = e.response.text if e.response.text else error_msg
            
            return f"I'm having trouble connecting to my thoughts right now. {detailed_error}"