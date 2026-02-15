"""
LLM Client
Handles communication with LLM API and tool calling
"""
import os
import json
from datetime import datetime
from config.settings import settings
from config.prompts import SYSTEM_PROMPT, TOOL_DEFINITIONS
from together import Together

class LLMClient:
    """Client for LLM API with tool calling support"""
    
    def __init__(self):
        if not settings.TOGETHER_API_KEY:
            raise ValueError("TOGETHER_API_KEY not configured")
        
        # self.client = OpenAI(
        # api_key=os.environ["OPENAI_API_KEY"],
        # base_url="https://api.together.xyz/v1",
        # )
        self.client = Together(api_key=settings.TOGETHER_API_KEY)
        self.model = settings.MODEL_NAME
    
    def chat_with_tools(self, messages, context=None):
        """
        Chat with LLM using tool calling

        Args:
            messages: List of conversation messages
            context: Current conversation context dict

        Returns:
            dict: {"content": str, "tool_calls": list}
        """
        # Prepare system prompt with current date
        current_date = datetime.now().strftime("%Y-%m-%d")
        system_prompt = SYSTEM_PROMPT.format(current_date=current_date)

        # Add context awareness if restaurants are available
        if context and context.get("available_options"):
            num_restaurants = len(context["available_options"])
            restaurant_names = [r.get("name", "") for r in context["available_options"][:3]]

            system_prompt += f"\n\n🔴 IMPORTANT CONTEXT - READ THIS:\n"
            system_prompt += f"There are currently {num_restaurants} restaurants available from a previous search:\n"
            for i, name in enumerate(restaurant_names):
                system_prompt += f"  {i+1}. {name}\n"
            system_prompt += f"\nIf the user is selecting one of these restaurants (e.g., says '1', 'first one', or the restaurant name), DO NOT call search_restaurants again."
            system_prompt += f"\n\n🔴 BOOKING INFORMATION STATUS:\n"
            system_prompt += f"- Party size: {context.get('party_size', 'NOT SET')}\n"
            system_prompt += f"- Date: {context.get('date', 'NOT SET')}\n"
            system_prompt += f"- Time: {context.get('time', 'NOT SET')}\n"
            system_prompt += f"\nTo complete a booking, you MUST extract customer name and phone from the conversation."
            system_prompt += f"\nCheck the conversation history carefully for any name or phone number the user provided."

        # Build messages with system prompt
        filtered_messages = []
        for i, m in enumerate(messages[-10:]):
            # Defensive filter: never send assistant messages that include a 'tool_calls' envelope. 
            if m.get('role') == 'assistant' and m.get('tool_calls'):
                continue
            # Always include tool role messages (tool results)
            if m.get('role') == 'tool':
                filtered_messages.append(m)
            # If a message contains tool_calls, only include it when it also contains human-readable content.
            elif m.get('tool_calls'):
                if m.get('content'):
                    filtered_messages.append(m)
                    content_preview = m.get('content', '')[:50] + '...' if len(m.get('content', '')) > 50 else m.get('content', '')
                else:
            # Include regular messages with content (skip internal 'analysis' notes)
            elif m.get('content') and not str(m.get('content')).startswith('analysis'):
                filtered_messages.append(m)
                content_preview = m.get('content', '')[:50] + '...' if len(m.get('content', '')) > 50 else m.get('content', '')
            else:
                preview = str(m.get('content', 'None'))[:30]

        full_messages = [{"role": "system", "content": system_prompt}] + filtered_messages

        # Normalize and deduplicate TOOL_DEFINITIONS before sending to the model.
        try:
            # TOOL_DEFINITIONS may be authored with a wrapper {"type":"function","function":{...}}
            tools_payload = []
            seen = set()
            # Determine whether to expose lookup/cancellation tools based on context
            def _has_valid_phone(ctx):
                if not ctx:
                    return False
                p = ctx.get('extracted_phone') or ctx.get('phone') or None
                return isinstance(p, str) and p.isdigit() and len(p) == 10

            can_expose_lookup_tools = _has_valid_phone(context)

            for t in TOOL_DEFINITIONS:
                # If the author already provided the wrapper {"type":"function","function":{...}}, keep it as-is
                if isinstance(t, dict) and t.get("type") and t.get("function"):
                    func_def = t.get("function")
                    name = func_def.get("name") if isinstance(func_def, dict) else None
                    # Do not expose find/cancel unless we have a validated phone in context
                    if name in ("find_reservation", "cancel_reservation") and not can_expose_lookup_tools:
                        continue
                    if name and name not in seen:
                        seen.add(name)
                        tools_payload.append(t)
                else:
                    # Otherwise, normalize by wrapping the inner function definition
                    func_def = t.get("function") if isinstance(t, dict) and t.get("function") else t
                    name = func_def.get("name") if isinstance(func_def, dict) else None
                    # Gate lookup/cancel tool exposure
                    if name in ("find_reservation", "cancel_reservation") and not can_expose_lookup_tools:
                        continue
                    if name and name not in seen:
                        seen.add(name)
                        tools_payload.append({"type": "function", "function": func_def})

            # Debug: show what tool defs we're sending to the model (extract names whether wrapped or not)
            try:
                tool_names = [ (x.get("function") and x.get("function").get("name")) or x.get("name") for x in tools_payload ]
            except Exception:
                print(f"\n[DEBUG] Sending tool definitions (couldn't extract names)")

            response = self.client.chat.completions.create(
                model=self.model,
                messages=full_messages,
                tools=tools_payload,
                tool_choice="auto",
                temperature=0.7,
                max_tokens=1024
            )
            
            try:
                raw_repr = str(response)
            except Exception as e:
                print(f"\n[DEBUG] Couldn't stringify raw response: {e}")

            message = response.choices[0].message


            try:
                msg_type = type(message)
                attrs = [a for a in dir(message) if not a.startswith('_')][:30]
            except Exception:
                pass

            result = {
                "content": message.content,
                "tool_calls": []
            }

            # Extract tool calls if present (robust to variations in SDK shapes)
            if getattr(message, "tool_calls", None):
                print(f"[DEBUG] Processing {len(message.tool_calls)} tool call(s):")
                for tool_call in message.tool_calls:
                    try:
                        if isinstance(tool_call, dict):
                        else:
                            # attribute-like object
                            try:
                                print(f"  - raw tool_call repr (truncated): {repr(tool_call)[:1000]}")
                            except Exception:
                                pass
                    except Exception:
                        pass
                    func_name = None
                    func_args = {}
                    call_id = None

                    # Support both dict-like and attribute-like tool_call shapes
                    try:
                        if isinstance(tool_call, dict):
                            call_id = tool_call.get('id') or tool_call.get('call_id')
                            # function may itself be a dict
                            func = tool_call.get('function') or {}
                            if isinstance(func, dict):
                                func_name = func.get('name')
                                raw_args = func.get('arguments') or tool_call.get('arguments') or tool_call.get('kwargs')
                            else:
                                func_name = tool_call.get('name')
                                raw_args = tool_call.get('arguments') or tool_call.get('kwargs')
                        else:
                            # attribute-like object
                            call_id = getattr(tool_call, 'id', None) or getattr(tool_call, 'call_id', None)
                            func_name = getattr(tool_call, 'name', None)
                            func_attr = getattr(tool_call, 'function', None)
                            if func_attr is not None:
                                raw_args = getattr(func_attr, 'arguments', None) or getattr(tool_call, 'arguments', None) or getattr(tool_call, 'kwargs', None)
                                if getattr(func_attr, 'name', None) and not func_name:
                                    func_name = getattr(func_attr, 'name', None)
                            else:
                                raw_args = getattr(tool_call, 'arguments', None) or getattr(tool_call, 'kwargs', None)
                    except Exception as e:
                        print(f"  - ERROR extracting tool_call fields: {e}")
                        raw_args = None

                    # Parse arguments into dict if possible
                    if raw_args is not None:
                        try:
                            if isinstance(raw_args, str):
                                func_args = json.loads(raw_args)
                            elif isinstance(raw_args, dict):
                                func_args = raw_args
                            else:
                                func_args = json.loads(str(raw_args))
                        except Exception as e:
                            print(f"  - ERROR parsing arguments: {e}")
                            func_args = {}


                    result["tool_calls"].append(
                        {
                            "id": call_id,
                            "function": func_name if func_name is not None else "undefined",
                            "arguments": func_args,
                            "raw": repr(tool_call)[:2000]
                        }
                    )
            elif message.content:
                print(f"[DEBUG] Conversational response: {message.content[:100]}...")

            return result

        except Exception as e:
            print(f"LLM API Error: {e}")
            return {
                "content": "I'm having trouble connecting right now. Please try again in a moment.",
                "tool_calls": [],
            }
