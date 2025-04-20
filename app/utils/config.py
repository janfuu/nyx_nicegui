import json
import os
import yaml
from pathlib import Path
from dotenv import load_dotenv

class Config:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance
    
    def _load_config(self):
        """Load configuration from config.yaml or config.json and .env"""
        # Load environment variables from .env file
        load_dotenv()
        
        # First try to load config.yaml
        yaml_config_path = Path(__file__).parent.parent / "config.yaml"
        json_config_path = Path(__file__).parent.parent / "config.json"
        
        self.config = {}
        
        # Try loading the YAML configuration first
        if yaml_config_path.exists():
            try:
                with open(yaml_config_path, 'r') as file:
                    self.config = yaml.safe_load(file)
                print(f"Loaded configuration from {yaml_config_path}")
            except Exception as e:
                print(f"Error loading YAML config: {str(e)}")
                # If YAML fails, we'll try JSON next
        
        # If YAML config doesn't exist or failed to load, try loading JSON
        if not self.config and json_config_path.exists():
            try:
                with open(json_config_path, 'r') as file:
                    self.config = json.load(file)
                print(f"Loaded configuration from {json_config_path}")
            except Exception as e:
                print(f"Error loading JSON config: {str(e)}")
                # If both config files fail, we'll continue with an empty config
        
        if not self.config:
            print("Warning: No configuration loaded. Using empty configuration.")
            self.config = {}
            
        # Load API keys from environment variables if available
        self.config.setdefault("llm", {})
        self.config["llm"]["api_key"] = os.environ.get("OPENAI_API_KEY", self.config["llm"].get("api_key", ""))
        # Add OpenRouter API key from environment variable
        self.config["llm"]["openrouter_api_key"] = os.environ.get("OPENROUTER_API_KEY", self.config["llm"].get("openrouter_api_key", ""))
        
        # Ensure image_generation section exists
        self.config.setdefault("image_generation", {})
        # Add Runware API key from environment variable
        self.config["image_generation"]["runware_api_key"] = os.environ.get("RUNWARE_API_KEY", self.config["image_generation"].get("runware_api_key", ""))
        self.config["image_generation"]["stability_api_key"] = os.environ.get("STABILITY_API_KEY", self.config["image_generation"].get("stability_api_key", ""))
        
        # Update HTTP Referer from environment variable if available
        self.config["llm"]["http_referer"] = os.environ.get("HTTP_REFERER", self.config["llm"].get("http_referer", "http://localhost:8080"))
    
    def get(self, section, key=None, default=None):
        """Get a configuration value"""
        if key is None:
            return self.config.get(section, default)
        return self.config.get(section, {}).get(key, default)
        
    def save(self):
        """Save the current configuration to the config.yaml file"""
        yaml_config_path = Path(__file__).parent.parent / "config.yaml"
        
        try:
            with open(yaml_config_path, 'w') as file:
                yaml.dump(self.config, file, default_flow_style=False, sort_keys=False)
            print(f"Configuration saved to {yaml_config_path}")
            return True
        except Exception as e:
            print(f"Error saving configuration: {str(e)}")
            return False