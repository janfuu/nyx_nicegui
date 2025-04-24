"""
Logger Service
=============

This module implements a singleton logging service that provides:
1. Multi-level logging (debug, info, warning, error)
2. Dual output (file and console)
3. Structured conversation logging
4. Raw payload archiving

The logger uses Python's built-in logging module with custom formatting
and file handling. It maintains separate logs for:
- General application logs (debug, info, warnings, errors)
- Detailed conversation turns
- Raw payloads for technical debugging

Log files are organized in the 'logs' directory:
- nyx_YYYYMMDD_HHMMSS.log: Main application log
- logs/raw/payload_YYYYMMDD_HHMMSS_ffffff.json: Raw conversation payloads
"""

import logging
import os
import json
from datetime import datetime
from pathlib import Path

class Logger:
    """
    Singleton logging service for the Nyx AI system.
    
    This class provides a centralized logging service that:
    1. Maintains a single instance across the application
    2. Handles multiple log levels and outputs
    3. Provides structured logging for conversations
    4. Archives raw payloads for debugging
    
    The logger is designed to be thread-safe and provides consistent
    logging across all components of the system.
    """
    _instance = None
    
    def __new__(cls):
        """Ensure singleton pattern - only one logger instance exists."""
        if cls._instance is None:
            cls._instance = super(Logger, cls).__new__(cls)
            cls._instance._setup_logging()
        return cls._instance
    
    def _setup_logging(self):
        """
        Initialize logging configuration.
        
        Sets up:
        1. Log directory structure
        2. File and console handlers
        3. Log formatting
        4. Log levels for different outputs
        """
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
        """Log an informational message."""
        self.logger.info(message)
    
    def debug(self, message):
        """Log a debug message (only visible in file logs)."""
        self.logger.debug(message)
        
    def warning(self, message):
        """Log a warning message."""
        self.logger.warning(message)
        
    def error(self, message, exc_info=True):
        """Log an error message with optional exception info."""
        self.logger.error(message, exc_info=exc_info)
    
    def log_conversation(self, system_prompt, user_message, conversation_history, llm_response, provider, model):
        """
        Log a complete conversation turn with all details.
        
        This method logs:
        1. A summary to the main log file
        2. Detailed conversation information
        3. Raw payload for technical debugging
        
        Args:
            system_prompt: The system prompt used for this conversation
            user_message: The user's input message
            conversation_history: List of previous messages
            llm_response: The AI's response
            provider: The LLM provider used
            model: The specific model used
        """
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
        """
        Log raw payloads for technical debugging.
        
        This method:
        1. Creates a raw logs directory if needed
        2. Saves the complete payload as JSON
        3. Uses microsecond precision in filenames
        
        Args:
            log_entry: Dictionary containing the complete conversation data
        """
        raw_logs_dir = Path('logs/raw')
        raw_logs_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        raw_log_file = raw_logs_dir / f"payload_{timestamp}.json"
        
        with open(raw_log_file, 'w') as f:
            json.dump(log_entry, f, indent=2)