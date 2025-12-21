# /config/pyscript_modules/furnace_config_io.py

import json

CONFIG_PATH = "/config/pyscript/data/furnace_preheat_config.json"

def load_config():
    """Native Python I/O – allowed to use open()."""
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except Exception as e:
        # print() in a native module is real stdout; in HA you'll see it in log
        print(f"furnace_config_io: error loading {CONFIG_PATH}: {e}")
        return {}
