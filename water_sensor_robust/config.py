import json
import os
from logger import Logger

def load_config():
    logger = Logger()
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
        logger = Logger()
        logger.log("Configuration loaded successfully.")
        #logger.log(config)
        return config
    except Exception as e:
        logger = Logger()
        logger.log(f"Error loading config: {e}")
        return None

def save_config(config):
    logger = Logger()
    try:
        with open('config.json', 'w') as f:
            json.dump(config, f)
        logger.log("Configuration saved successfully.")
        return True
    except Exception as e:
        logger.log(f"Error saving config: {e}")
        return False