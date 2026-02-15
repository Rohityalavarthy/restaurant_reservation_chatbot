"""
Tool: Find Reservation
"""

from utils.database import load_reservations

def execute(phone_or_id):
    """Find reservation by phone or ID"""
    try:
        reservations = load_reservations()
        
        match = next(
            (r for r in reservations
             if r.get("confirmation_id") == phone_or_id
             or r.get("phone") == phone_or_id),
            None
        )
        
        if match:
            return True
        else:
            return False
        
    except Exception as e:
        return {"error": f"Search failed: {str(e)}"}
