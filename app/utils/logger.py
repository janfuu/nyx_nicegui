import logging
import os
import json
from datetime import datetime
from pathlib import Path

class Logger:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Logger, cls).__new__(cls)
            cls._instance._setup_logging()
        return cls._instance
    
    def _setup_logging(self):
        # Create logs directory if it doesn't exist
        logs_dir = Path('logs')
        logs_dir.mkdir(exist_ok=True)
        
        # Set up file handler for detailed logs
        self.log_file = logs_dir / f"nyx_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        # Configure standard Python logger
        self.logger = logging.getLogger('nyx')
        self.logger.setLevel(logging.DEBUG)
        
        # Add file handler
        file_handler = logging.FileHandler(self.log_file)
        file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        
        # Add console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(file_formatter)
        console_handler.setLevel(logging.INFO)
        self.logger.addHandler(console_handler)
        
        self.logger.info(f"Logger initialized. Logs will be saved to {self.log_file}")
    
    def info(self, message):
        self.logger.info(message)
    
    def debug(self, message):
        self.logger.debug(message)
        
    def warning(self, message):
        self.logger.warning(message)
        
    def error(self, message, exc_info=True):
        self.logger.error(message, exc_info=exc_info)
    
    def log_conversation(self, system_prompt, user_message, conversation_history, llm_response, provider, model):
        """Log a complete conversation turn with all details"""
        # Create a detailed log entry as a dictionary
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "provider": provider,
            "model": model,
            "system_prompt": system_prompt,
            "conversation_history": conversation_history,
            "user_message": user_message,
            "llm_response": llm_response
        }
        
        # Log a summary to the regular log
        self.logger.info(f"Conversation: User: '{user_message[:30]}...' → AI: '{llm_response[:30]}...'")
        
        # Write the detailed log entry to the log file
        with open(self.log_file, 'a') as f:
            f.write(f"\n--- CONVERSATION TURN AT {datetime.now().isoformat()} ---\n")
            f.write(f"PROVIDER: {provider}\n")
            f.write(f"MODEL: {model}\n\n")
            f.write("SYSTEM PROMPT:\n")
            f.write(f"{system_prompt}\n\n")
            f.write("CONVERSATION HISTORY:\n")
            for msg in conversation_history:
                f.write(f"[{msg['role']}]: {msg['content']}\n")
            f.write("\nUSER MESSAGE:\n")
            f.write(f"{user_message}\n\n")
            f.write("AI RESPONSE:\n")
            f.write(f"{llm_response}\n")
            f.write("-" * 80 + "\n")
        
        # Additionally, log raw payloads for debugging
        self._log_raw_payload(log_entry)
        
    def _log_raw_payload(self, log_entry):
        """Log raw payloads for technical debugging"""
        raw_logs_dir = Path('logs/raw')
        raw_logs_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        raw_log_file = raw_logs_dir / f"payload_{timestamp}.json"
        
        with open(raw_log_file, 'w') as f:
            json.dump(log_entry, f, indent=2)