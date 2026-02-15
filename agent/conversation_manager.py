"""
Conversation Manager - LLM-First Architecture
"""
import re
import json
from agent.llm_client import LLMClient
from tools import (
    search_restaurants,
    create_reservation,
    find_reservation,
    update_reservation,
    cancel_reservation,
    select_restaurant
)

class ConversationManager:
    """Manages conversation flow - LLM-first approach"""
    
    def __init__(self):
        self.llm = LLMClient()
        self.context = {
            "party_size": None,
            "location": None,
            "date": None,
            "time": None,
            "available_options": []  # Stores restaurant search results
        }
        self.conversation_history = []
        # Flag indicating we asked the user for a phone/confirmation specifically to look up a reservation
        self.awaiting_lookup_phone = False
    
    def process_message(self, user_message: str) -> str:

        print(f"\n{'='*70}")
        print(f"[USER] {user_message}")
        print(f"[CONTEXT] Available restaurants: {len(self.context.get('available_options', []))}")
        print(f"{'='*70}\n")

        print(f"[DEBUG] Conversation Manager - Current context state:")
        print(f"  - Party size: {self.context.get('party_size')}")
        print(f"  - Location: {self.context.get('location')}")
        print(f"  - Date: {self.context.get('date')}")
        print(f"  - Time: {self.context.get('time')}")
        print(f"  - Available restaurants: {len(self.context.get('available_options', []))}")
        print(f"  - Conversation history length: {len(self.conversation_history)}")

        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })


        # Conservative extraction: try to find an explicit phone or name in recent user messages
        try:
            aggregated = self._gather_customer_info()
            if aggregated.get('phone'):
                # persist an extracted phone into context so downstream logic can expose lookup tools
                self.context['extracted_phone'] = aggregated.get('phone')
            if aggregated.get('customer_name'):
                self.context['extracted_customer_name'] = aggregated.get('customer_name')
        except Exception:
            # Extraction is best-effort; do not fail the whole flow if it errors
            pass

        try:
            phone = self.context.get('extracted_phone')
            if self.awaiting_lookup_phone and phone:
                self.awaiting_lookup_phone = False
                tool_result = self._execute_tool('find_reservation', {'phone_or_id': phone})
                self.conversation_history.append({"role": "tool", "tool_call_id": None, "content": str(tool_result)})

                # If a reservation was found, auto-cancel as requested
                #reservation = tool_result
                if tool_result:
                    # Determine confirmation id from reservation record
                    #reservation_id = reservation.get('confirmation_id') or reservation.get('reservation_id') or reservation.get('id')
                    reservation_id = phone
                    if reservation_id:
                        cancel_result = self._execute_tool('cancel_reservation', {'reservation_id': reservation_id})
                        # store cancel result
                        self.conversation_history.append({"role": "tool", "tool_call_id": None, "content": str(cancel_result)})
                        formatted_cancel = self._format_tool_response('cancel_reservation', cancel_result)
                        self.conversation_history.append({"role": "assistant", "content": formatted_cancel})
                        return formatted_cancel

                # No reservation found or no reservation_id — return the lookup response as before
                formatted = self._format_tool_response('find_reservation', tool_result)
                self.conversation_history.append({"role": "assistant", "content": formatted})
                return formatted
        except Exception:
            # best-effort: don't block flow on unexpected errors here
            pass

        # Pass everything to LLM - it will intelligently decide what to do
        clean_history = self._get_clean_history()
        
        response = self.llm.chat_with_tools(
            messages=clean_history,
            context=self.context
        )
        
        # Handle tool calls
        if response.get("tool_calls"):
            tool_call = response["tool_calls"][0]
            # Debug: show parsed tool_call dict received from LLM client
            try:
                print(f"\n[DEBUG] Parsed tool_call (from LLM client): {json.dumps(tool_call, indent=2, default=str)}")
            except Exception:
                print(f"\n[DEBUG] Parsed tool_call (repr): {repr(tool_call)[:1000]}")
            function_name = tool_call.get("function")
            arguments = tool_call.get("arguments", {})

            # Defensive check for find_reservation: ensure the LLM provided a real phone or confirmation id
            if function_name == "find_reservation":
                # Accept multiple possible keys
                phone_or_id = arguments.get('phone_or_id') or arguments.get('phone') or arguments.get('confirmation_id') or arguments.get('id')
                # Helper validator
                def _is_valid_phone_or_confirmation(val):
                    if not val or not isinstance(val, str):
                        return False
                    s = val.strip()
                    # valid 10-digit phone
                    if s.isdigit() and len(s) == 10:
                        return True
                    if re.search(r"user('|\")?s|number|phone number|confirmation id|confirmation|phone-or-id|phone_or_id|provided", s, re.IGNORECASE):
                        return False
                    if re.match(r"^[A-Za-z0-9-]{4,}$", s):
                        return True
                    return False

                if not _is_valid_phone_or_confirmation(phone_or_id):
                    # Ask the user for explicit phone/confirmation and do NOT call the tool
                    prompt = "Sure — could you provide your 10-digit phone number or your confirmation ID so I can look up your reservation?"
                    # Set a flag so the manager knows the next phone message should trigger a lookup
                    self.awaiting_lookup_phone = True
                    self.conversation_history.append({"role": "assistant", "content": prompt})
                    print("[DEBUG] find_reservation call had no valid phone/ID; asking user for explicit info and skipping tool call")
                    return prompt

            if function_name == "search_restaurants" and self.context.get("available_options"):
                try:
                    same_search = (
                        str(arguments.get("location")).lower() == str(self.context.get("location") or "").lower()
                        and str(arguments.get("date")) == str(self.context.get("date"))
                        and str(arguments.get("time")) == str(self.context.get("time"))
                        and (arguments.get("party_size") == self.context.get("party_size"))
                    )
                except Exception:
                    same_search = False

                if same_search:
                    # Look for the latest user message
                    latest_user = None
                    for m in reversed(self.conversation_history):
                        if m.get('role') == 'user' and m.get('content'):
                            latest_user = m.get('content')
                            break

                    if latest_user:
                        inference = self._infer_selection_from_message(latest_user)
                        # Aggregate explicit info from recent user messages as a fallback
                        aggregated = self._gather_customer_info()
                        # Merge aggregated info into inference if fields missing
                        if aggregated.get('phone') and not inference.get('phone'):
                            inference['phone'] = aggregated['phone']
                        if aggregated.get('customer_name') and not inference.get('customer_name'):
                            inference['customer_name'] = aggregated['customer_name']
                        # If we don't have an index but a previous tentative selection was stored, use it
                        if inference.get('restaurant_index') is None and self.context.get('selected_restaurant_index') is not None:
                            inference['restaurant_index'] = self.context.get('selected_restaurant_index')

                        if inference and inference.get('restaurant_index') is not None:
                            # Persist tentative selection so later messages (name/phone) can complete booking
                            try:
                                self.context['selected_restaurant_index'] = int(inference.get('restaurant_index'))
                            except Exception:
                                pass
                            # Only proceed to booking when phone (10 digits) is present and name looks valid
                            phone_ok = bool(inference.get('phone') and isinstance(inference.get('phone'), str) and len(inference.get('phone')) == 10 and inference.get('phone').isdigit())
                            name_ok = bool(inference.get('customer_name') and isinstance(inference.get('customer_name'), str) and len(inference.get('customer_name').strip()) > 0 and ' and ' not in inference.get('customer_name').lower())

                            if phone_ok and name_ok:
                                booking_args = {
                                    "restaurant_index": inference['restaurant_index'],
                                    "customer_name": inference['customer_name'].strip(),
                                    "phone": inference['phone'],
                                    "special_requests": inference.get('special_requests', '')
                                }
                                # Store a short assistant note and execute booking
                                self.conversation_history.append({"role": "assistant", "content": f"Interpreting your reply and proceeding to book: index={booking_args['restaurant_index']}"})
                                tool_result = self._execute_tool('select_restaurant', booking_args)
                                # Store tool result and formatted response as usual
                                self.conversation_history.append({"role": "tool", "tool_call_id": None, "content": str(tool_result)})
                                formatted = self._format_tool_response('select_restaurant', tool_result)
                                self.conversation_history.append({"role": "assistant", "content": formatted})
                                return formatted
                            else:
                                # Missing or invalid name/phone — ask only for the missing piece(s)
                                if not phone_ok and not name_ok:
                                    question = "Great — could you please provide your name and 10-digit phone number so I can complete the booking?"
                                elif not phone_ok:
                                    question = "Great — please provide your 10-digit phone number to complete the booking."
                                else:
                                    question = "Great — please provide your name to complete the booking."
                                self.conversation_history.append({"role": "assistant", "content": question})
                                return question
                        else:
                            # We couldn't infer selection; prompt user to confirm choice
                            prompt = "I already have a few options. Which one would you like (1, 2, or the restaurant name)? Also please provide your name and 10-digit phone number to complete the booking."
                            self.conversation_history.append({"role": "assistant", "content": prompt})
                            return prompt


            # If LLM produced undefined function, dump raw tool_call for debugging
            if function_name is None or function_name == "undefined":
                raw = tool_call.get('raw') or tool_call.get('function') or None

            # CRITICAL: Validate function name is valid
            # Accept both variants used in prompts / LLM and keep legacy names
            valid_functions = [
                "search_restaurants",
                "select_restaurant_and_book",
                "select_restaurant",
                "find_reservation",
                "update_reservation",
                "cancel_reservation",
            ]
            if function_name not in valid_functions:
                print(f"[DEBUG] ❌ INVALID FUNCTION NAME: {function_name}")
                print(f"[DEBUG] Valid functions are: {valid_functions}")
                print(f"[DEBUG] Returning conversational response instead of calling invalid function\n")

                # Return a helpful message based on context (use context available_options)
                restaurants = self.context.get("available_options", [])
                if restaurants:
                    restaurant_name = restaurants[0].get("name", "your selected restaurant")
                    error_message = f"I'd be happy to help you book at {restaurant_name}! To complete your reservation, could you please provide your name and phone number?"
                else:
                    error_message = "I'd be happy to help you with your reservation! Could you please provide your name and phone number?"

                self.conversation_history.append({
                    "role": "assistant",
                    "content": error_message
                })

                return error_message

            # Store the assistant's tool call in history with a short human-readable summary
            try:
                # Build a concise summary string (avoid overly long dumps)
                args_preview = ', '.join([f"{k}={v}" for k, v in (arguments or {}).items()])
                assistant_summary = f"Calling {function_name} with {args_preview}" if args_preview else f"Calling {function_name}"
            except Exception:
                assistant_summary = f"Calling {function_name}"

            # Store only a human-readable assistant summary here. Do NOT include
            # the 'tool_calls' wrapper in assistant messages — that shape causes
            # the model to treat the assistant as still performing tool actions.
            self.conversation_history.append({
                "role": "assistant",
                "content": assistant_summary
            })

            # If the model asked to cancel but didn't provide an id, and we
            # previously extracted a phone, inject it so the cancel tool can
            # operate by phone. This leverages the updated cancel_reservation
            # implementation that accepts phone/phone_or_id.
            if function_name == 'cancel_reservation':
                if not arguments.get('reservation_id') and not arguments.get('reservationId') and not arguments.get('confirmation_id'):
                    phone = self.context.get('extracted_phone')
                    if phone:
                        # prefer phone_or_id arg name expected by tools
                        arguments = arguments.copy() if isinstance(arguments, dict) else dict(arguments or {})
                        arguments['phone_or_id'] = phone

            # Execute the tool
            tool_result = self._execute_tool(function_name, arguments)

            # Store the tool result in history (with special "tool" role)
            self.conversation_history.append({
                "role": "tool",
                "tool_call_id": tool_call.get("id"),
                "content": str(tool_result)
            })

            # Format response for user display
            formatted_response = self._format_tool_response(function_name, tool_result)

            # Add a final assistant message with the formatted response
            self.conversation_history.append({
                "role": "assistant",
                "content": formatted_response
            })

            return formatted_response
        
        # No tool calls - conversational response
        assistant_message = response.get("content", "I'm here to help with your reservation!")

        self.conversation_history.append({
            "role": "assistant",
            "content": assistant_message
        })

        return assistant_message
    
    def _execute_tool(self, function_name, arguments):
        """Execute tool function"""

        print(f"\n[DEBUG] _execute_tool called with: {function_name}")
        print(f"[DEBUG] Arguments: {arguments}")
        if function_name == "search_restaurants":
            # Store search parameters in context
            self.context["party_size"] = arguments.get("party_size")
            self.context["location"] = arguments.get("location")
            self.context["date"] = arguments.get("date")
            self.context["time"] = arguments.get("time")


            result = search_restaurants.execute(**arguments)

            # Store available restaurants for later selection
            self.context["available_options"] = result.get("restaurants", [])
            for i, r in enumerate(self.context["available_options"]):
                print(f"  [{i}] {r.get('name', 'Unknown')}")

            return result
            
        # Accept both canonical and legacy booking function names
        elif function_name in ("select_restaurant", "select_restaurant_and_book"):
            print(f"[DEBUG] Executing booking/select tool ({function_name})...")
            # LLM extracted: restaurant_index, customer_name, phone
            return self._handle_restaurant_booking(arguments)

        elif function_name == "find_reservation":
            print(f"[DEBUG] Executing find_reservation tool...")
            return find_reservation.execute(**arguments)

        elif function_name == "update_reservation":
            print(f"[DEBUG] Executing update_reservation tool...")
            return update_reservation.execute(**arguments)

        elif function_name == "cancel_reservation":
            print(f"[DEBUG] Executing cancel_reservation tool...")
            return cancel_reservation.execute(**arguments)
        
        elif function_name == "create_reservation":
            return create_reservation.execute(**arguments)
        
        else:
            print(f"[DEBUG] ERROR: Unknown function: {function_name}")
            return {"error": f"Unknown function: {function_name}"}
    
    def _handle_restaurant_booking(self, arguments):
        """Handle restaurant selection + booking"""

        print(f"\n[DEBUG] _handle_restaurant_booking called")
        print(f"[DEBUG] Raw arguments: {arguments}")

        restaurant_index = arguments.get("restaurant_index")
        customer_name = arguments.get("customer_name")
        phone = arguments.get("phone")
        special_requests = arguments.get("special_requests", "")

        # CRITICAL: Check if name/phone were actually mentioned in conversation
        name_found_in_conversation = self._is_in_conversation(customer_name) if customer_name else False
        phone_found_in_conversation = self._is_in_conversation(phone) if phone else False

        # Reject if name or phone were not actually mentioned by user (protect against hallucination)
        if not name_found_in_conversation:
            print(f"[BOOKING] ❌ Name '{customer_name}' was NOT found in conversation history!")
            return {"error": "I don't see a customer name in our conversation. Could you please provide your name?"}

        if not phone_found_in_conversation:
            print(f"[BOOKING] ❌ Phone '{phone}' was NOT found in conversation history!")
            return {"error": "I don't see a phone number in our conversation. Could you please provide your 10-digit phone number?"}
        
        # Validate phone number
        if not phone or len(phone) != 10 or not phone.isdigit():
            print(f"[BOOKING] ❌ Invalid phone: '{phone}'")
            print(f"  - Is None/empty: {not phone}")
            print(f"  - Length: {len(phone) if phone else 0}")
            print(f"  - Is digit: {phone.isdigit() if phone else False}\n")
            return {
                "error": f"Invalid phone number '{phone}'. Please provide a 10-digit phone number."
            }

        # Get available restaurants from context
        available_restaurants = self.context.get("available_options", [])

        if not available_restaurants:
            print("[BOOKING] ❌ No restaurants in context\n")
            return {
                "error": "No restaurants available. Please search for restaurants first."
            }

        # Validate index
        if restaurant_index < 0 or restaurant_index >= len(available_restaurants):
            print(f"[BOOKING] ❌ Invalid index: {restaurant_index} (must be 0-{len(available_restaurants)-1})\n")
            return {
                "error": f"Invalid restaurant selection. Please choose from the available options (1-{len(available_restaurants)})."
            }

        # Get selected restaurant
        selected_restaurant = available_restaurants[restaurant_index]
        restaurant_id = selected_restaurant["restaurant_id"]

        print(f"\n[BOOKING] ✅ Selected: {selected_restaurant['name']}")
        print(f"  ID: {restaurant_id}")
        print(f"  Location: {selected_restaurant.get('location', 'Unknown')}\n")
        
        # Create reservation

        result = create_reservation.execute(
            restaurant_id=restaurant_id,
            customer_name=customer_name,
            phone=phone,
            date=self.context.get("date"),
            time=self.context.get("time"),
            party_size=self.context.get("party_size"),
            special_requests=special_requests
        )

        print(f"\n[BOOKING] Reservation complete!")
        print(f"  - Status: {'SUCCESS' if result.get('confirmation_id') else 'ERROR'}")
        print(f"  - Confirmation ID: {result.get('confirmation_id', 'N/A')}")
        if 'error' in result:
            print(f"  - Error: {result.get('error')}")
        print()

        return result
    
    def _format_tool_response(self, function_name, result):
        """Format tool execution result into user-friendly message"""

        if "error" in result:
            print(f"[DEBUG] Formatting error response: {result['error']}")
            # Return the error message directly - it already contains the user-friendly ask
            return result['error']
        
        if function_name == "search_restaurants":
            return self._format_search_results(result)
            
        elif function_name == "select_restaurant_and_book" or function_name == "select_restaurant":
            return self._format_booking_confirmation(result)
            
        elif function_name == "find_reservation":
            return self._format_reservation_details(result)
            
        elif function_name == "update_reservation":
            return self._format_update_confirmation(result)
            
        elif function_name == "cancel_reservation":
            return self._format_cancellation_confirmation(result)
        
        return "✅ Done!"
    
    def _format_search_results(self, result):
        """Format restaurant search results"""
        restaurants = result.get("restaurants", [])
        
        if not restaurants:
            return "I couldn't find any availability for that time. Would you like to try a different time or location?"
        
        response = f"I found **{len(restaurants)} great option(s)**:\n\n"
        
        for i, rest in enumerate(restaurants[:5], 1):
            times = rest.get("available_times", [])
            time_str = ", ".join(times[:3]) if times else "Check availability"
            
            response += f"**{i}. {rest['name']}** 📍\n"
            response += f"   • Location: {rest.get('address', 'N/A')}\n"
            response += f"   • Available: {time_str}\n"
            response += f"   • Capacity: {rest.get('seating_capacity', 'N/A')} seats\n"
            
            features = rest.get("features", [])
            if features:
                response += f"   • Features: {', '.join(features[:2])}\n"
            
            response += "\n"
        
        response += "Which one would you like? Please also provide your name and phone number so I can complete the booking!"
        
        return response
    
    def _format_booking_confirmation(self, result):
        """Format booking confirmation"""
        conf_id = result.get("confirmation_id")
        details = result.get("booking_details", {})
        
        response = f"""✅ **Booking Confirmed!**

🎫 **Confirmation ID:** `{conf_id}`

📍 **Restaurant:** {details.get('restaurant_name')}
📅 **Date:** {details.get('date')}
🕐 **Time:** {details.get('time')}
👥 **Party Size:** {details.get('party_size')} people"""

        if details.get('special_requests'):
            response += f"\n\n📝 **Special Requests:** {details.get('special_requests')}"
        
        response += "\n\nSee you soon! 🎉\n\n*(You'll receive SMS confirmation shortly)*"
        
        return response
    
    def _format_reservation_details(self, result):
        """Format reservation lookup result"""
        reservation = result.get("reservation")
        
        if not reservation:
            return "I couldn't find a reservation with that information. Could you provide your confirmation ID or phone number?"
        
        response = f"""**Your Reservation** 📋

🎫 **Confirmation ID:** `{reservation.get('confirmation_id')}`
📍 **Restaurant:** {reservation.get('restaurant_name')}
📅 **Date:** {reservation.get('date')}
🕐 **Time:** {reservation.get('time')}
👥 **Party Size:** {reservation.get('party_size')} people
📱 **Phone:** {reservation.get('phone')}
📌 **Status:** {reservation.get('status', 'confirmed').upper()}"""

        if reservation.get('special_requests'):
            response += f"\n\n📝 **Special Requests:** {reservation.get('special_requests')}"
        
        response += "\n\nNeed to modify or cancel? Just let me know!"
        
        return response
    
    def _format_update_confirmation(self, result):
        """Format reservation update confirmation"""
        details = result.get("updated_details", {})
        
        return f"""✅ **Reservation Updated!**

🎫 **Confirmation ID:** `{result.get('confirmation_id')}`

**New Details:**
📅 **Date:** {details.get('date')}
🕐 **Time:** {details.get('time')}
👥 **Party Size:** {details.get('party_size')} people

All set! See you then! 🎉"""
    
    def _format_cancellation_confirmation(self, result):
        """Format cancellation confirmation"""
        return f"""✅ **Reservation Cancelled**

🎫 **Confirmation ID:** `{result.get('confirmation_id')}`

Your reservation has been cancelled. We're sorry we'll miss you!

Would you like to make a new booking for a different date? I'm here to help! 😊"""
    
    def _is_in_conversation(self, value: str) -> bool:
        """Check if a value actually appears in the user's conversation history"""
        if not value:
            return False

        # Search through all user messages for this value
        for msg in self.conversation_history:
            if msg.get('role') == 'user':
                content = msg.get('content', '').lower()
                if value.lower() in content:
                    return True
        return False

    def _infer_selection_from_message(self, message: str) -> dict:
        """Heuristic extraction: infer restaurant_index, customer_name, phone, special_requests from a user message.

        Returns a dict with any of the keys: restaurant_index (int), customer_name (str), phone (str), special_requests (str)
        """

        out = {}
        text = (message or "").strip()
        text_low = text.lower()

        # Phone: 10 consecutive digits
        m = re.search(r"\b(\d{10})\b", text)
        if m:
            out['phone'] = m.group(1)

        # Name: look after "i'm", "i am", "my name is"
        # Be conservative: capture up to common delimiters (comma, 'and', 'my', digits)
        name = None
        m = re.search(r"(?:i\s*'?m|i\s+am|my name is)\s+([A-Za-z][A-Za-z'\-]*(?:\s+[A-Za-z][A-Za-z'\-]*)?)", text, re.IGNORECASE)
        if m:
            name_candidate = m.group(1).strip()
            name_candidate = re.split(r"\band\b|\bmy\b|,|\d", name_candidate, flags=re.IGNORECASE)[0].strip()
            tokens = [t for t in name_candidate.split() if re.match(r"^[A-Za-z'\-]+$", t)]
            if tokens:
                out['customer_name'] = " ".join(tokens[:2])

        # Special requests: look for phrases like 'birthday', 'vegan', 'window', 'outdoor'
        sr = []
        if 'birthday' in text_low:
            sr.append('birthday')
        if 'vegan' in text_low or 'vegetarian' in text_low:
            sr.append('dietary: vegetarian/vegan')
        if 'window' in text_low or 'outdoor' in text_low:
            sr.append('seating preference')
        if sr:
            out['special_requests'] = ", ".join(sr)

        # Restaurant selection by index words or numbers
        idx = None
        if re.search(r"\bfirst\b|\b1st\b|\b1\b", text_low):
            idx = 0
        elif re.search(r"\bsecond\b|\b2nd\b|\b2\b", text_low):
            idx = 1
        elif re.search(r"\bthird\b|\b3rd\b|\b3\b", text_low):
            idx = 2

        # Restaurant name match against available options
        if idx is None:
            try:
                for i, r in enumerate(self.context.get('available_options', [])):
                    name_lower = r.get('name', '').lower()
                    if name_lower and name_lower in text_low:
                        idx = i
                        break
            except Exception:
                pass

        if idx is not None:
            out['restaurant_index'] = idx

        return out

    def _gather_customer_info(self, lookback: int = 6) -> dict:
        """Scan recent user messages and aggregate explicit phone and name values.

        Returns a dict with optional keys: 'phone' and 'customer_name'.
        This is conservative: phone must be 10 digits; name must look like letters-only tokens.
        """
        import re
        phone = None
        name = None

        recent = [m for m in self.conversation_history if m.get('role') == 'user'][-lookback:]
        # Search for phone first (10-digit)
        for m in reversed(recent):
            content = m.get('content', '')
            pm = re.search(r"\b(\d{10})\b", content)
            if pm:
                phone = pm.group(1)
                break

        # Search for name tokens across recent messages
        for m in reversed(recent):
            content = m.get('content', '')
            nm = re.search(r"(?:i\s*'?m|i\s+am|my name is)\s+([A-Za-z][A-Za-z'\-]*(?:\s+[A-Za-z][A-Za-z'\-]*)?)", content, re.IGNORECASE)
            if nm:
                candidate = nm.group(1).strip()
                candidate = re.split(r"\band\b|\bmy\b|,|\d", candidate, flags=re.IGNORECASE)[0].strip()
                tokens = [t for t in candidate.split() if re.match(r"^[A-Za-z'\-]+$", t)]
                if tokens:
                    name = " ".join(tokens[:2])
                    break

        # Search for restaurant selection index (e.g., 'first', '1', 'second') in recent messages
        idx = None
        for m in reversed(recent):
            content = (m.get('content') or '').lower()
            if re.search(r"\bfirst\b|\b1st\b|\b1\b", content):
                idx = 0
                break
            if re.search(r"\bsecond\b|\b2nd\b|\b2\b", content):
                idx = 1
                break
            if re.search(r"\bthird\b|\b3rd\b|\b3\b", content):
                idx = 2
                break

        # Also try matching restaurant names against available options
        if idx is None:
            try:
                for m in reversed(recent):
                    content = (m.get('content') or '').lower()
                    for i, r in enumerate(self.context.get('available_options', [])):
                        name_lower = r.get('name', '').lower()
                        if name_lower and name_lower in content:
                            idx = i
                            break
                    if idx is not None:
                        break
            except Exception:
                pass

        if idx is not None:
            # include as integer index
            return {k: v for k, v in (('phone', phone), ('customer_name', name), ('restaurant_index', idx)) if v}

        return {k: v for k, v in (('phone', phone), ('customer_name', name)) if v}

    def _get_clean_history(self):
        """Get clean conversation history (last 10 messages)"""
        clean = self.conversation_history[-10:]
        print(f"[DEBUG] _get_clean_history returning {len(clean)} messages")
        for i, msg in enumerate(clean):
            role = msg.get('role')
            has_content = bool(msg.get('content'))
            has_tools = bool(msg.get('tool_calls'))
            print(f"  [{i}] role={role}, has_content={has_content}, has_tools={has_tools}")
        return clean
    
    def reset(self):
        """Reset conversation state"""
        self.context = {
            "party_size": None,
            "location": None,
            "date": None,
            "time": None,
            "available_options": []
        }
        self.conversation_history = []
