"""
Find available restaurants matching criteria
"""

from datetime import datetime, timedelta
from utils.database import load_restaurants

def execute(location, date, time, party_size):


    try:
        restaurants = load_restaurants()

        # Filter by location
        location_lower = location.lower()
        matches = [
            r for r in restaurants
            if (location_lower in r.get("location", "").lower() or
                location_lower in r.get("city", "").lower())
        ]


        if not matches:
            all_cities = list(set(r.get("city", "") for r in restaurants))
            return {
                "restaurants": [],
                "error": f"No restaurants found in {location}. We have locations in: {', '.join(all_cities)}"
            }
        
        # Filter by capacity
        matches = [r for r in matches if r.get("seating_capacity", 0) >= party_size]


        if not matches:
            return {
                "restaurants": [],
                "error": f"No restaurants in {location} can accommodate {party_size} people."
            }

        # Generate available time slots
        for restaurant in matches:
            time_slots = _generate_time_slots(time)
            restaurant["available_times"] = time_slots

        # Sort by capacity
        matches.sort(key=lambda x: x.get("seating_capacity", 0), reverse=True)

        print(f"[TOOL:search_restaurants] Returning {len(matches[:5])} restaurants")
        for i, r in enumerate(matches[:5]):
            print(f"  [{i}] {r.get('name')} (capacity: {r.get('seating_capacity')})")

        return {"restaurants": matches[:5]}
        
    except Exception as e:
        print(f"[TOOL:search_restaurants] ❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"error": f"Search failed: {str(e)}"}

def _generate_time_slots(requested_time):
    """Generate available time slots around requested time"""
    try:
        hour, minute = map(int, requested_time.split(":"))
        
        slots = []
        for offset in [-30, -15, 0, 15, 30]:
            new_min = minute + offset
            new_hour = hour
            
            while new_min < 0:
                new_hour -= 1
                new_min += 60
            
            while new_min >= 60:
                new_hour += 1
                new_min -= 60
            
            if 11 <= new_hour < 23:
                slots.append(f"{new_hour:02d}:{new_min:02d}")
        
        return sorted(set(slots))
        
    except Exception:
        return ["19:00", "19:30", "20:00", "20:30", "21:00"]
