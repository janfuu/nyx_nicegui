import json
import os
from pathlib import Path

class Config:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance
    
    def _load_config(self):
        """Load configuration from config.json"""
        config_path = Path(__file__).parent.parent / "config.json"
        
        with open(config_path, 'r') as file:
            self.config = json.load(file)
            
        # Load API keys from environment variables if available
        self.config["llm"]["api_key"] = os.environ.get("OPENAI_API_KEY", self.config["llm"].get("api_key", ""))
        # Add OpenRouter API key from environment variable
        self.config["llm"]["openrouter_api_key"] = os.environ.get("OPENROUTER_API_KEY", self.config["llm"].get("openrouter_api_key", ""))
        # Add Runware API key from environment variable
        self.config["image_generation"]["runware_api_key"] = os.environ.get("RUNWARE_API_KEY", self.config["image_generation"].get("runware_api_key", ""))
        self.config["image_generation"]["stability_api_key"] = os.environ.get("STABILITY_API_KEY", self.config["image_generation"].get("stability_api_key", ""))
    
    def get(self, section, key=None, default=None):
        """Get a configuration value"""
        if key is None:
            return self.config.get(section, default)
        return self.config.get(section, {}).get(key, default)