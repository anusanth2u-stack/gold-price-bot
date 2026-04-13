import json
import os

CACHE_FILE = "price_cache.json"


def load_cache():
    if not os.path.exists(CACHE_FILE):
        return {}

    try:
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    except:
        return {}


def save_cache(data):
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(data, f)
    except:
        pass


def get_cached(key):
    return load_cache().get(key)


def set_cached(key, value):
    data = load_cache()
    data[key] = value
    save_cache(data)