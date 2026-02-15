"""
Database Utilities
JSON file-based database operations
"""

import json
from config.settings import settings

def load_restaurants():
    """Load restaurants from JSON"""
    try:
        with open(settings.RESTAURANTS_DB, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        print(f"Error reading {settings.RESTAURANTS_DB}")
        return []

def load_reservations():
    """Load reservations from JSON"""
    try:
        with open(settings.RESERVATIONS_DB, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        print(f"Error reading {settings.RESERVATIONS_DB}")
        return []

def save_reservations(reservations):
    """Save reservations to JSON"""
    try:
        with open(settings.RESERVATIONS_DB, 'w') as f:
            json.dump(reservations, f, indent=2)
    except Exception as e:
        print(f"Error saving reservations: {e}")
        raise

def load_constraints():
    """Load booking constraints from JSON"""
    try:
        with open(settings.CONSTRAINTS_DB, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        print(f"Error reading {settings.CONSTRAINTS_DB}")
        return {}
