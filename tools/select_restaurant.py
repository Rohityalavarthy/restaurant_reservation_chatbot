"""
Intelligently handles restaurant selection + booking in one step
"""

def execute(restaurant_index, customer_name, phone, special_requests=""):
    """
    Select restaurant from available options and create booking
    
    Args:
        restaurant_index: Index of selected restaurant (0, 1, or 2)
        customer_name: Customer's name
        phone: Customer's 10-digit phone number
        special_requests: Optional special requests
    
    Returns:
        dict: Booking confirmation or error
    """
    
    # This tool needs access to conversation context
    # It will be called from conversation_manager which has the context
    
    return {
        "status": "tool_executed",
        "restaurant_index": restaurant_index,
        "customer_name": customer_name,
        "phone": phone,
        "special_requests": special_requests
    }
