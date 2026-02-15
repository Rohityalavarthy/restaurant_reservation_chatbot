"""
Tool: Create Reservation
"""

import uuid
from datetime import datetime
from utils.database import load_reservations, save_reservations, load_restaurants

def execute(restaurant_id, customer_name, phone, date, time, party_size, special_requests=""):
    """Create a new reservation"""
    print(f"[TOOL:create_reservation] Executing with params:")
    print(f"  - restaurant_id: {restaurant_id}")
    print(f"  - customer_name: {customer_name}")
    print(f"  - phone: {phone}")
    print(f"  - date: {date}")
    print(f"  - time: {time}")
    print(f"  - party_size: {party_size}")
    print(f"  - special_requests: {special_requests}")

    try:
        reservations = load_reservations()
        restaurants = load_restaurants()

        print(f"[TOOL:create_reservation] Loaded {len(reservations)} existing reservations")
        print(f"[TOOL:create_reservation] Searching for restaurant with ID: {restaurant_id}")

        restaurant = next(
            (r for r in restaurants if r["restaurant_id"] == restaurant_id),
            None
        )

        if not restaurant:
            print(f"[TOOL:create_reservation] ❌ Restaurant not found with ID: {restaurant_id}")
            return {"error": "Restaurant not found"}

        print(f"[TOOL:create_reservation] ✅ Found restaurant: {restaurant.get('name')}")
        
        # Generate confirmation ID
        city_code = restaurant["city"][:3].upper()
        date_code = date.replace("-", "")[2:]
        random_code = str(uuid.uuid4())[:4].upper()
        confirmation_id = f"GF-{city_code}-{date_code}-{random_code}"

        print(f"[TOOL:create_reservation] Generated confirmation ID: {confirmation_id}")

        reservation = {
            "confirmation_id": confirmation_id,
            "restaurant_id": restaurant_id,
            "restaurant_name": restaurant["name"],
            "customer_name": customer_name,
            "phone": phone,
            "date": date,
            "time": time,
            "party_size": party_size,
            "special_requests": special_requests,
            "status": "confirmed",
            "created_at": datetime.now().isoformat()
        }

        print(f"[TOOL:create_reservation] Saving reservation to database...")
        reservations.append(reservation)
        save_reservations(reservations)

        print(f"[TOOL:create_reservation] ✅ Reservation saved successfully!")
        print(f"  - Total reservations now: {len(reservations)}")

        return {
            "confirmation_id": confirmation_id,
            "status": "confirmed",
            "booking_details": {
                "restaurant_name": restaurant["name"],
                "date": date,
                "time": time,
                "party_size": party_size,
                "special_requests": special_requests
            }
        }
        
    except Exception as e:
        print(f"[TOOL:create_reservation] ❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"error": f"Booking failed: {str(e)}"}
