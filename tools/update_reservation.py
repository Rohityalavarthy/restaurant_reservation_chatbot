"""
Tool: Update Reservation
"""

from utils.database import load_reservations, save_reservations

def execute(reservation_id, new_date=None, new_time=None, new_party_size=None):
    """Update existing reservation"""
    try:
        reservations = load_reservations()
        
        reservation = next(
            (r for r in reservations if r["confirmation_id"] == reservation_id),
            None
        )
        
        if not reservation:
            return {"error": "Reservation not found"}
        
        if new_date:
            reservation["date"] = new_date
        if new_time:
            reservation["time"] = new_time
        if new_party_size:
            reservation["party_size"] = new_party_size
        
        save_reservations(reservations)
        
        return {
            "confirmation_id": reservation_id,
            "updated_details": {
                "date": reservation["date"],
                "time": reservation["time"],
                "party_size": reservation["party_size"]
            }
        }
        
    except Exception as e:
        return {"error": f"Update failed: {str(e)}"}
