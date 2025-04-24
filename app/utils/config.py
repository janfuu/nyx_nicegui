"""
Configuration Management
======================

This module provides a centralized configuration management system that:
1. Loads configuration from YAML/JSON files
2. Integrates with environment variables
3. Provides a singleton pattern for global access
4. Handles API key management
5. Supports configuration persistence

The system prioritizes configuration sources in this order:
1. Environment variables (highest priority)
2. YAML configuration file
3. JSON configuration file
4. Default values (lowest priority)

This ensures flexible configuration management while maintaining security
for sensitive data like API keys.
"""

import json
import os
import yaml
from pathlib import Path
from dotenv import load_dotenv

class Config:
    """
    Singleton configuration manager for the application.
    
    This class implements the Singleton pattern to ensure a single source
    of configuration throughout the application. It handles:
    1. Loading configuration from multiple sources
    2. Managing API keys and sensitive data
    3. Providing type-safe access to configuration values
    4. Supporting configuration persistence
    
    The configuration is loaded once at initialization and can be
    accessed globally through the singleton instance.
    """
    _instance = None
    
    def __new__(cls):
        """
        Implement the Singleton pattern.
        
        Ensures only one instance of the Config class exists throughout
        the application lifecycle. The first call creates the instance,
        subsequent calls return the existing instance.
        """
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance
    
    def _load_config(self):
        """
        Load and merge configuration from multiple sources.
        
        This method:
        1. Loads environment variables from .env file
        2. Attempts to load YAML configuration
        3. Falls back to JSON configuration if YAML fails
        4. Merges API keys from environment variables
        5. Sets default values for missing configurations
        
        The configuration is stored in the instance's config dictionary
        with a hierarchical structure (section -> key -> value).
        """
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
        """
        Retrieve a configuration value.
        
        This method provides safe access to configuration values with
        support for default values and hierarchical configuration.
        
        Args:
            section: The configuration section (e.g., 'llm', 'image_generation')
            key: The specific configuration key within the section
            default: Default value to return if the key is not found
            
        Returns:
            The configuration value if found, otherwise the default value
        """
        if key is None:
            return self.config.get(section, default)
        return self.config.get(section, {}).get(key, default)
        
    def save(self):
        """
        Persist the current configuration to disk.
        
        Saves the current configuration state to the YAML configuration file.
        This allows runtime configuration changes to be preserved between
        application restarts.
        
        Returns:
            bool: True if the save was successful, False otherwise
        """
        yaml_config_path = Path(__file__).parent.parent / "config.yaml"
        
        try:
            with open(yaml_config_path, 'w') as file:
                yaml.dump(self.config, file, default_flow_style=False, sort_keys=False)
            print(f"Configuration saved to {yaml_config_path}")
            return True
        except Exception as e:
            print(f"Error saving configuration: {str(e)}")
            return False