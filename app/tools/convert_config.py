#!/usr/bin/env python3
"""
Utility script to convert config.json to config.yaml
This is a one-time operation to migrate from JSON to YAML configuration format
"""

import json
import yaml
import os
from pathlib import Path

def convert_config():
    """Convert config.json to config.yaml if it exists"""
    project_root = Path(__file__).parent.parent
    json_config_path = project_root / "config.json"
    yaml_config_path = project_root / "config.yaml"
    
    # Check if JSON config exists
    if not json_config_path.exists():
        print(f"JSON configuration file not found at {json_config_path}")
        return False
    
    # Check if YAML config already exists
    if yaml_config_path.exists():
        user_input = input(f"YAML configuration file already exists at {yaml_config_path}. Overwrite? (y/n): ")
        if user_input.lower() != 'y':
            print("Conversion cancelled.")
            return False
    
    # Read JSON config
    try:
        with open(json_config_path, 'r') as json_file:
            config_data = json.load(json_file)
    except Exception as e:
        print(f"Error reading JSON config: {str(e)}")
        return False
    
    # Write YAML config
    try:
        with open(yaml_config_path, 'w') as yaml_file:
            yaml.dump(config_data, yaml_file, default_flow_style=False, sort_keys=False)
    except Exception as e:
        print(f"Error writing YAML config: {str(e)}")
        return False
    
    print(f"Successfully converted {json_config_path} to {yaml_config_path}")
    
    # Ask if user wants to create a backup of the JSON config
    user_input = input("Create a backup of the JSON config file? (y/n): ")
    if user_input.lower() == 'y':
        backup_path = json_config_path.with_suffix(".json.bak")
        try:
            import shutil
            shutil.copy2(json_config_path, backup_path)
            print(f"Backup created at {backup_path}")
        except Exception as e:
            print(f"Error creating backup: {str(e)}")
    
    # Ask if user wants to delete the JSON config
    user_input = input("Delete the original JSON config file? (y/n): ")
    if user_input.lower() == 'y':
        try:
            os.remove(json_config_path)
            print(f"Deleted {json_config_path}")
        except Exception as e:
            print(f"Error deleting file: {str(e)}")
    
    return True

if __name__ == "__main__":
    print("Config Converter - JSON to YAML")
    print("==============================")
    convert_config() 