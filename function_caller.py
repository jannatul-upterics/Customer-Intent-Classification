"""
LLM Function Calling Decision Engine & Execution Flow for Restaurant Booking.

Complete Flow:
1. Customer message
        ↓
2. LLM decides function & arguments
        ↓
3. Function name + arguments matched to Python function
        ↓
4. Python executes function with error handling
        ↓
5. Function result captured
        ↓
6. Function result sent back to LLM
        ↓
7. LLM generates natural final customer response

Error Handling:
- Unknown function name
- Missing arguments
- Invalid arguments (types / validation)
- Invalid JSON/arguments
- Function execution errors
"""

import os
import re
import json
import time
import inspect
from typing import Optional, Dict, Any, List
import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from restaurant_functions import (
    RESTAURANT_TOOLS,
    check_availability,
    create_booking,
    modify_booking,
    cancel_booking
)

# Function registry mapping LLM tool names to Python callables
FUNCTION_REGISTRY = {
    "check_availability": check_availability,
    "create_booking": create_booking,
    "modify_booking": modify_booking,
    "cancel_booking": cancel_booking
}

# Required fields per function
REQUIRED_TOOL_FIELDS = {
    "check_availability": ["date", "time", "party_size"],
    "create_booking": ["customer_name", "date", "time", "party_size"],
    "modify_booking": ["booking_id"],
    "cancel_booking": ["booking_id"]
}

SYSTEM_ROUTER_PROMPT = """You are an AI restaurant assistant for a premier dining venue, equipped with function calling capabilities.

You have access to the following tools:
1. check_availability(date, time, party_size): Check if a table is free for a specified date, time, and guest count.
2. create_booking(customer_name, date, time, party_size): Create and confirm a new table reservation when the customer provides their name and booking parameters.
3. modify_booking(booking_id, new_date, new_time, new_party_size): Update an existing booking using its booking ID (e.g. "ABC123", "BK-1001").
4. cancel_booking(booking_id): Cancel an existing booking using its booking ID.

CRITICAL OPERATIONAL RULES:
- Only call a function when the customer's request clearly warrants it.
- Never call a function unnecessarily (e.g. for general questions about operating hours, menus, greetings, or unrelated questions). Reply directly with helpful text.
- NEVER invent, assume, or hallucinate missing parameter values (such as customer names, dates, times, party sizes, or booking IDs).
- If the customer asks to book without providing a name, do NOT call create_booking. If date, time, and party size are present, call check_availability, or ask for the missing name.
- If the customer wants to cancel or modify a reservation without giving their booking ID, reply directly asking for their booking ID.
- Standardize all time values to strict 24-hour "HH:MM" format (e.g., "8 PM" -> "20:00", "7:30 PM" -> "19:30").
- When you receive a function execution result in a tool message, formulate a friendly, concise, natural response explaining or confirming the result to the customer. Never output raw code or raw JSON to the customer.
"""


def normalize_time_str(time_val: Any) -> Optional[str]:
    """Standardizes conversational or 12-hour time into 24-hour HH:MM format."""
    if not time_val:
        return None
    time_str = str(time_val).strip()

    # Already HH:MM
    if re.match(r"^(?:[01]\d|2[0-3]):[0-5]\d$", time_str):
        return time_str

    # 12-hour format with AM/PM or conversational suffixes
    match_12h = re.match(
        r"^(\d{1,2})(?::(\d{2}))?\s*(?:in the evening|in the afternoon|in the morning)?\s*(am|pm)?$",
        time_str,
        re.IGNORECASE
    )
    if match_12h:
        h = int(match_12h.group(1))
        m = int(match_12h.group(2) or 0)
        meridiem = (match_12h.group(3) or "").lower()
        is_evening = "evening" in time_str.lower() or "pm" in time_str.lower()
        if (is_evening or meridiem == "pm") and h < 12:
            h += 12
        elif (not is_evening and meridiem == "am") and h == 12:
            h = 0
        return f"{h:02d}:{m:02d}"

    return time_str


def normalize_arguments(action: str, raw_args: Dict[str, Any]) -> Dict[str, Any]:
    """Cleans, standardizes, and normalizes function arguments."""
    normalized = {}

    # Map number_of_guests and party_size aliases in input
    if "number_of_guests" in raw_args and ("party_size" not in raw_args or raw_args["party_size"] is None):
        raw_args["party_size"] = raw_args["number_of_guests"]
    if "new_number_of_guests" in raw_args and ("new_party_size" not in raw_args or raw_args["new_party_size"] is None):
        raw_args["new_party_size"] = raw_args["new_number_of_guests"]
    if "guests" in raw_args and ("party_size" not in raw_args or raw_args["party_size"] is None):
        raw_args["party_size"] = raw_args["guests"]

    # Handle parameter aliases (e.g. LLM passing 'party_size' to modify_booking instead of 'new_party_size')
    if action == "modify_booking":
        if "party_size" in raw_args and "new_party_size" not in raw_args:
            raw_args["new_party_size"] = raw_args["party_size"]
        if "date" in raw_args and "new_date" not in raw_args:
            raw_args["new_date"] = raw_args["date"]
        if "time" in raw_args and "new_time" not in raw_args:
            raw_args["new_time"] = raw_args["time"]

    # Normalize time fields
    if "time" in raw_args and raw_args["time"] is not None:
        normalized["time"] = normalize_time_str(raw_args["time"])
    if "new_time" in raw_args and raw_args["new_time"] is not None:
        normalized["new_time"] = normalize_time_str(raw_args["new_time"])

    # Normalize party size fields
    if "party_size" in raw_args and raw_args["party_size"] is not None:
        try:
            val = int(raw_args["party_size"])
            normalized["party_size"] = val
            normalized["number_of_guests"] = val
        except (ValueError, TypeError):
            normalized["party_size"] = raw_args["party_size"]
            normalized["number_of_guests"] = raw_args["party_size"]

    if "new_party_size" in raw_args and raw_args["new_party_size"] is not None:
        try:
            val = int(raw_args["new_party_size"])
            normalized["new_party_size"] = val
            normalized["new_number_of_guests"] = val
        except (ValueError, TypeError):
            normalized["new_party_size"] = raw_args["new_party_size"]
            normalized["new_number_of_guests"] = raw_args["new_party_size"]

    # String fields
    for field in ("customer_name", "date", "new_date", "booking_id"):
        if field in raw_args and raw_args[field] is not None:
            val = str(raw_args[field]).strip()
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                val = val[1:-1].strip()
            normalized[field] = val

    return normalized


def execute_function(function_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Matches the function name to the corresponding Python callable and executes it with error handling:
    - Unknown function name
    - Missing required arguments
    - Invalid arguments (types/values)
    - Function execution errors
    """
    # 1. Unknown function name handling
    if function_name not in FUNCTION_REGISTRY:
        return {
            "success": False,
            "error_type": "unknown_function",
            "error": f"Unknown function '{function_name}'. Supported functions: {list(FUNCTION_REGISTRY.keys())}",
            "action": function_name
        }

    target_func = FUNCTION_REGISTRY[function_name]
    sig = inspect.signature(target_func)

    # 2. Explicit required argument validation per function
    REQUIRED_PER_ACTION = {
        "check_availability": ["date", "time", "party_size"],
        "create_booking": ["customer_name", "date", "time", "party_size"],
        "modify_booking": ["booking_id"],
        "cancel_booking": ["booking_id"]
    }
    missing = [
        f for f in REQUIRED_PER_ACTION.get(function_name, [])
        if f not in arguments or arguments[f] is None or str(arguments[f]).strip() == ""
    ]

    if missing:
        return {
            "success": False,
            "error_type": "missing_arguments",
            "error": f"Missing required argument(s) for '{function_name}': {', '.join(missing)}",
            "action": function_name,
            "missing_fields": missing
        }

    # 3. Filter arguments to only those accepted by the target function
    filtered_args = {k: v for k, v in arguments.items() if k in sig.parameters}

    # 4. Safe execution handling invalid arguments and runtime exceptions
    try:
        result = target_func(**filtered_args)
        return result
    except (TypeError, ValueError) as err:
        return {
            "success": False,
            "error_type": "invalid_arguments",
            "error": f"Invalid argument for '{function_name}': {err}",
            "action": function_name
        }
    except Exception as err:
        return {
            "success": False,
            "error_type": "execution_error",
            "error": f"Function execution error in '{function_name}': {err}",
            "action": function_name
        }


def _build_fallback_conversation_summary(
    customer_messages: List[str],
    function_name: Optional[str],
    arguments: Optional[Dict[str, Any]],
    current_state: Optional[Dict[str, Any]] = None,
    state_history: Optional[List[Dict[str, Any]]] = None
) -> str:
    """Builds a factual fallback summary of the full conversation using deterministic heuristics."""
    args = dict(arguments or {})
    if current_state:
        for k, v in current_state.items():
            if k not in args or args[k] is None:
                args[k] = v

    changes = []

    # Check for party size changes across messages or state history
    party_sizes = []
    if state_history:
        for h in state_history:
            ps = h.get("resulting_state", {}).get("party_size")
            if ps is not None and (not party_sizes or party_sizes[-1] != ps):
                party_sizes.append(ps)
    if not party_sizes:
        for msg in customer_messages:
            m = re.search(r"\b(?:table for|party of|make it|change(?: it)? to|for)\s+(\d+)\b", msg, re.I)
            if m:
                val = int(m.group(1))
                if not party_sizes or party_sizes[-1] != val:
                    party_sizes.append(val)

    if len(party_sizes) >= 2 and party_sizes[0] != party_sizes[-1]:
        changes.append(f"The party size was originally {party_sizes[0]} but was changed to {party_sizes[-1]}.")

    # Check for dietary removal
    for msg in customer_messages:
        if re.search(r"\b(?:no|never mind|remove|without|cancel)\s+(?:any\s+)?(?:allerg|diet|gluten|vegan)\b", msg, re.I):
            changes.append("The dietary preference was removed.")
            break

    # Check for intent change
    if len(customer_messages) > 1:
        last_turn = customer_messages[-1].lower()
        prior_turns = " ".join(customer_messages[:-1]).lower()
        if "cancel" in last_turn and ("change" in prior_turns or "modify" in prior_turns or "book" in prior_turns):
            changes.append("The customer originally planned to update their reservation but changed their intention to cancel.")

    # Base sentence according to action
    if function_name == "check_availability":
        base = "The customer wants to check table availability"
        parts = []
        if args.get("party_size"):
            parts.append(f"for {args['party_size']} people")
        if args.get("date"):
            d_str = str(args['date'])
            parts.append(f"this {d_str}" if d_str.lower() in ("saturday", "friday", "sunday") else f"on {d_str}")
        if args.get("time"):
            parts.append(f"at {args['time']}")
        base_sentence = f"{base} {' '.join(parts)}."
    elif function_name == "create_booking":
        base = "The customer wants to book a table"
        parts = []
        if args.get("party_size"):
            parts.append(f"for {args['party_size']} people")
        if args.get("date"):
            d_str = str(args['date'])
            parts.append(f"this {d_str}" if d_str.lower() in ("saturday", "friday", "sunday") else f"on {d_str}")
        if args.get("time"):
            parts.append(f"at {args['time']}")
        if args.get("customer_name"):
            parts.append(f"under the name {args['customer_name']}")
        base_sentence = f"{base} {' '.join(parts)}."
    elif function_name == "modify_booking":
        bid = args.get("booking_id", "the reservation")
        parts = []
        if args.get("new_party_size"):
            parts.append(f"to {args['new_party_size']} people")
        if args.get("new_date"):
            parts.append(f"to {args['new_date']}")
        if args.get("new_time"):
            parts.append(f"at {args['new_time']}")
        base_sentence = f"The customer wants to modify booking {bid} {' '.join(parts)}."
    elif function_name == "cancel_booking":
        bid = args.get("booking_id", "the reservation")
        base_sentence = f"The customer requested to cancel booking {bid}."
    else:
        base_sentence = "The customer inquired about restaurant information."

    if changes:
        return f"{base_sentence} {' '.join(changes)}"
    return base_sentence


def generate_conversation_summary(
    customer_message: str,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    function_name: Optional[str] = None,
    arguments: Optional[Dict[str, Any]] = None,
    current_state: Optional[Dict[str, Any]] = None,
    state_history: Optional[List[Dict[str, Any]]] = None,
    preferred_model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None
) -> str:
    """
    Generates a concise 1-2 sentence factual summary of the FULL conversation so far.

    Considers:
    - All previous customer messages
    - Information provided earlier
    - Changes made later (e.g. party size originally 4 changed to 6)
    - Added requirements
    - Removed requirements (e.g. dietary restrictions removed)
    - The customer's latest request
    - Any relevant booking details already discussed
    """
    # 1. Reconstruct sequence of customer messages
    customer_messages = []
    if state_history:
        for item in state_history:
            if isinstance(item, dict) and item.get("message"):
                customer_messages.append(str(item["message"]).strip())
    elif conversation_history:
        for msg in conversation_history:
            if isinstance(msg, dict) and msg.get("role") == "user" and msg.get("content"):
                customer_messages.append(str(msg["content"]).strip())

    if customer_message and (not customer_messages or customer_messages[-1] != customer_message.strip()):
        customer_messages.append(customer_message.strip())

    if not customer_messages:
        customer_messages = [customer_message.strip()] if customer_message else ["Inquiry"]

    # 2. Try generating summary with LLM
    summary_text = None
    if api_key:
        system_summary_prompt = (
            "You are an AI assistant for a restaurant reservation system.\n"
            "Your task is to write a concise, factual summary of the FULL customer conversation.\n\n"
            "MANDATORY GUIDELINES:\n"
            "1. You must summarize the ENTIRE dialogue history, not just the last message.\n"
            "2. State the customer's current goal/request (e.g. checking availability, creating a booking, modifying, or cancelling) and the final confirmed parameters.\n"
            "3. If any detail was updated or changed during the conversation (e.g., party size changed, time shifted, date altered, or intent changed), YOU MUST EXPLICITLY MENTION what changed and its original value (e.g., 'The party size was originally 4 but was changed to 6.').\n"
            "4. If a requirement was removed or cancelled (e.g., dietary restriction removed), do not present it as active and briefly note it was removed.\n"
            "5. Do NOT hallucinate or assume details not mentioned.\n"
            "6. Keep the summary natural, concise, and within 1-2 sentences in third person ('The customer...').\n"
            "7. Output ONLY the plain text summary, with no prefixes, no quotes, and no formatting."
        )

        conv_formatted = "\n".join(f"- Customer: \"{m}\"" for m in customer_messages)
        user_content = (
            f"Full Customer Conversation:\n{conv_formatted}\n\n"
            f"Active Function: {function_name or 'none'}\n"
            f"Arguments: {json.dumps(arguments or {})}\n\n"
            "Summary:"
        )

        model_candidates = [
            preferred_model or "openai/gpt-oss-20b",
            "qwen/qwen3.8-27b",
            "groq/compound-mini",
            "openai/gpt-oss-120b"
        ]
        seen_models = set()
        model_candidates = [m for m in model_candidates if m and not (m in seen_models or seen_models.add(m))]

        endpoint = f"{(base_url or 'https://api.groq.com/openai/v1').rstrip('/')}/chat/completions"
        for m in model_candidates:
            try:
                resp = requests.post(
                    endpoint,
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={
                        "model": m,
                        "messages": [
                            {"role": "system", "content": system_summary_prompt},
                            {"role": "user", "content": user_content}
                        ],
                        "temperature": 0.0,
                        "max_tokens": 400
                    },
                    timeout=15
                )
                if resp.status_code == 200:
                    data = resp.json()
                    c = data["choices"][0]["message"].get("content", "").strip()
                    c = c.strip('"\'').replace("\u202f", " ").replace("\xa0", " ").strip()
                    if c and len(c) > 10:
                        summary_text = c
                        break
            except Exception:
                continue

    # 3. Fallback to deterministic heuristic summary if LLM call is unavailable or empty
    if not summary_text:
        summary_text = _build_fallback_conversation_summary(
            customer_messages=customer_messages,
            function_name=function_name,
            arguments=arguments,
            current_state=current_state,
            state_history=state_history
        )

    return summary_text


def process_customer_request(
    customer_message: str,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    current_state: Optional[Dict[str, Any]] = None,
    state_history: Optional[List[Dict[str, Any]]] = None,
    preferred_model: Optional[str] = None
) -> Dict[str, Any]:
    """
    Executes the complete end-to-end function calling flow with conversational state integration:
    1. Augments prompt with Current Conversation State and prior conversation history.
    2. Sends customer message to LLM with restaurant tools.
    3. LLM decides if a tool should be called and provides arguments (considering accumulated state).
    4. Merges any missing arguments from current_state so the user is never asked to repeat details.
    5. Python executes the matched function (with robust error handling).
    6. Function result is sent back to the LLM in a 'tool' message.
    7. LLM generates a natural final response for the customer.

    Returns:
        Structured result dict containing:
        - status: 'function_executed' | 'direct_response' | 'error'
        - function_called: str or None
        - arguments: dict
        - function_result: dict or None
        - final_response: str
        - model_used: str
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return {
            "status": "error",
            "error": "GROQ_API_KEY is not set. Please configure your key in .env.",
            "final_response": "I apologize, but the reservation system API key is not configured."
        }
    api_key = api_key.strip()

    base_url = "https://api.groq.com/openai/v1"
    preferred = preferred_model or os.environ.get("LLM_MODEL", "openai/gpt-oss-20b")
    models_to_try = [
        preferred,
        "groq/compound-mini",
        "openai/gpt-oss-120b",
        "groq/compound",
        "qwen/qwen3.8-27b",
        "openai/gpt-oss-safeguard-20b",
        "qwen/qwen3.6-27b"
    ]

    seen = set()
    models_to_try = [m for m in models_to_try if m and not (m in seen or seen.add(m))]

    # Build system prompt with active conversation state if available
    system_prompt = SYSTEM_ROUTER_PROMPT
    if current_state:
        active_state = {k: v for k, v in current_state.items() if v is not None and v != []}
        system_prompt += (
            f"\n\nCURRENT CONVERSATION STATE (Accumulated details from previous turns):\n"
            f"{json.dumps(active_state, indent=2)}\n\n"
            f"IMPORTANT MULTI-TURN RULES:\n"
            f"1. You MUST consider the conversation history and the Current Conversation State when deciding which function to call and when constructing function arguments.\n"
            f"2. When the customer asks about table availability (e.g. 'Is that available?', 'Do you have a table for that?', 'Is that free?'), you MUST invoke 'check_availability' using the accumulated date, time, and party_size from the Current Conversation State.\n"
            f"3. When the customer asks to finalize or confirm a reservation, invoke 'create_booking' using the accumulated date, time, party_size, and customer_name.\n"
            f"4. Do NOT ask the customer to repeat details (date, time, party size) that are already present in the Current Conversation State.\n"
            f"5. When modifying or cancelling a reservation across multiple turns, if booking_id is in Current Conversation State or prior messages, invoke 'modify_booking' or 'cancel_booking' using that booking_id.\n"
        )

    # Build initial message chain
    messages = [{"role": "system", "content": system_prompt}]
    if conversation_history:
        messages.extend(conversation_history)
    messages.append({"role": "user", "content": customer_message})

    # -----------------------------------------------------------------------
    # Step 1: Query LLM for Tool Call Decision
    # -----------------------------------------------------------------------
    step1_response = None
    selected_model = None
    last_error = None

    for model in models_to_try:
        try:
            resp = requests.post(
                f"{base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": messages,
                    "tools": RESTAURANT_TOOLS,
                    "tool_choice": "auto",
                    "temperature": 0.0
                },
                timeout=30
            )
        except requests.exceptions.RequestException as err:
            return {"status": "error", "error": f"API request failed: {err}"}

        if resp.status_code == 200:
            try:
                res_data = resp.json()
                step1_response = res_data["choices"][0]["message"]
                selected_model = model
                break
            except (KeyError, IndexError, json.JSONDecodeError) as err:
                last_error = f"Malformed API response: {err}"
                continue
        elif resp.status_code == 429:
            time.sleep(2.0)
            continue
        else:
            last_error = f"API error ({resp.status_code}): {resp.text}"
            continue

    if not step1_response:
        return {
            "status": "error",
            "error": last_error or "Failed to receive response from LLM.",
            "final_response": "I apologize, but I am unable to connect to the booking system right now."
        }

    tool_calls = step1_response.get("tool_calls")

    # If LLM did not call a tool directly, check if customer implicitly asked for availability with complete state
    if not tool_calls or len(tool_calls) == 0:
        msg_lower = customer_message.lower()
        is_asking_availability = bool(re.search(r"\b(?:is that available|available|do you have (?:a table|space)|any openings|can we get that)\b", msg_lower))
        has_full_state = (
            current_state
            and current_state.get("date")
            and current_state.get("time")
            and current_state.get("party_size")
        )

        if is_asking_availability and has_full_state:
            # Construct synthetic tool call based on current state
            fn_name = "check_availability"
            normalized_args = {
                "date": current_state["date"],
                "time": current_state["time"],
                "party_size": current_state["party_size"]
            }
            tool_call_id = f"call_state_{int(time.time())}"
            tool_calls = [{
                "id": tool_call_id,
                "type": "function",
                "function": {
                    "name": fn_name,
                    "arguments": json.dumps(normalized_args)
                }
            }]
        elif bool(re.search(r"\b(?:cancel|cancelling|cancellation)\b", msg_lower)) and (current_state and current_state.get("booking_id")):
            fn_name = "cancel_booking"
            normalized_args = {"booking_id": current_state["booking_id"]}
            tool_call_id = f"call_state_{int(time.time())}"
            tool_calls = [{
                "id": tool_call_id,
                "type": "function",
                "function": {
                    "name": fn_name,
                    "arguments": json.dumps(normalized_args)
                }
            }]
        else:
            direct_text = step1_response.get("content", "")
            summary_text = generate_conversation_summary(
                customer_message=customer_message,
                conversation_history=conversation_history,
                function_name=None,
                arguments={},
                current_state=current_state,
                state_history=state_history,
                preferred_model=selected_model,
                api_key=api_key,
                base_url=base_url
            )
            return {
                "status": "direct_response",
                "function": None,
                "function_called": None,
                "arguments": {},
                "summary": summary_text,
                "function_result": None,
                "final_response": direct_text,
                "model_used": selected_model
            }

    # -----------------------------------------------------------------------
    # Step 2: Read Tool Name, Tool Call ID, and Arguments
    # -----------------------------------------------------------------------
    first_tool = tool_calls[0]
    tool_call_id = first_tool.get("id")
    fn_info = first_tool.get("function", {})
    fn_name = fn_info.get("name")
    fn_args_raw = fn_info.get("arguments", "{}")

    # Error handling for invalid JSON
    if isinstance(fn_args_raw, str):
        try:
            parsed_args = json.loads(fn_args_raw)
        except json.JSONDecodeError as json_err:
            function_result = {
                "success": False,
                "error_type": "invalid_json",
                "error": f"Invalid JSON in function arguments: {json_err}",
                "action": fn_name
            }
            normalized_args = {"raw_arguments": fn_args_raw}
        else:
            normalized_args = normalize_arguments(fn_name, parsed_args)
    else:
        normalized_args = normalize_arguments(fn_name, fn_args_raw or {})

    # Fallback / merge missing arguments from current conversation state
    if current_state and isinstance(normalized_args, dict):
        if fn_name == "check_availability":
            if ("party_size" not in normalized_args or normalized_args["party_size"] is None) and current_state.get("party_size") is not None:
                normalized_args["party_size"] = current_state["party_size"]
            if ("date" not in normalized_args or not normalized_args["date"]) and current_state.get("date"):
                normalized_args["date"] = current_state["date"]
            if ("time" not in normalized_args or not normalized_args["time"]) and current_state.get("time"):
                normalized_args["time"] = current_state["time"]
        elif fn_name == "create_booking":
            if ("party_size" not in normalized_args or normalized_args["party_size"] is None) and current_state.get("party_size") is not None:
                normalized_args["party_size"] = current_state["party_size"]
            if ("date" not in normalized_args or not normalized_args["date"]) and current_state.get("date"):
                normalized_args["date"] = current_state["date"]
            if ("time" not in normalized_args or not normalized_args["time"]) and current_state.get("time"):
                normalized_args["time"] = current_state["time"]
            if ("customer_name" not in normalized_args or not normalized_args["customer_name"]) and current_state.get("customer_name"):
                normalized_args["customer_name"] = current_state["customer_name"]
        elif fn_name in ("modify_booking", "cancel_booking"):
            if ("booking_id" not in normalized_args or not normalized_args["booking_id"]) and current_state.get("booking_id"):
                normalized_args["booking_id"] = current_state["booking_id"]

    function_result = execute_function(fn_name, normalized_args)

    # -----------------------------------------------------------------------
    # Step 3 & 4: Send Function Result Back to LLM for Final Customer Response
    # -----------------------------------------------------------------------
    follow_up_messages = list(messages)
    follow_up_messages.append({
        "role": "assistant",
        "content": step1_response.get("content"),
        "tool_calls": tool_calls
    })
    follow_up_messages.append({
        "role": "tool",
        "tool_call_id": tool_call_id,
        "name": fn_name,
        "content": json.dumps(function_result)
    })

    final_response = None
    for model in [selected_model] + models_to_try:
        try:
            resp2 = requests.post(
                f"{base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": follow_up_messages,
                    "temperature": 0.2
                },
                timeout=30
            )
        except requests.exceptions.RequestException:
            continue

        if resp2.status_code == 200:
            try:
                res2_data = resp2.json()
                final_response = res2_data["choices"][0]["message"]["content"]
                break
            except (KeyError, IndexError, json.JSONDecodeError):
                continue
        elif resp2.status_code == 429:
            time.sleep(2.0)
            continue

    if not final_response:
        # Graceful fallback if step 2 API call encounters network error
        if function_result.get("success"):
            final_response = function_result.get("message", "Operation completed successfully.")
        else:
            final_response = f"Sorry, we could not complete your request: {function_result.get('error')}"

    summary_text = generate_conversation_summary(
        customer_message=customer_message,
        conversation_history=conversation_history,
        function_name=fn_name,
        arguments=normalized_args,
        current_state=current_state,
        state_history=state_history,
        preferred_model=selected_model,
        api_key=api_key,
        base_url=base_url
    )

    return {
        "status": "function_executed",
        "function": fn_name,
        "function_called": fn_name,
        "arguments": normalized_args,
        "summary": summary_text,
        "function_result": function_result,
        "final_response": final_response,
        "model_used": selected_model
    }


# Retain evaluate_customer_message for decision-only inspection
def evaluate_customer_message(
    message: str,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    current_state: Optional[Dict[str, Any]] = None,
    state_history: Optional[List[Dict[str, Any]]] = None,
    preferred_model: Optional[str] = None
) -> Dict[str, Any]:
    """Inspects LLM function decision and arguments without executing the flow."""
    res = process_customer_request(
        customer_message=message,
        conversation_history=conversation_history,
        current_state=current_state,
        state_history=state_history,
        preferred_model=preferred_model
    )
    if res.get("status") == "function_executed":
        fn_res = res.get("function_result", {})
        if not fn_res.get("success") and fn_res.get("error_type") == "missing_arguments":
            return {
                "status": "missing_information",
                "function": res.get("function") or res.get("function_called"),
                "function_called": res.get("function") or res.get("function_called"),
                "arguments": res.get("arguments"),
                "summary": res.get("summary", ""),
                "missing_fields": fn_res.get("missing_fields"),
                "message": fn_res.get("error"),
                "model_used": res.get("model_used")
            }
        return {
            "status": "function_call",
            "function": res.get("function") or res.get("function_called"),
            "function_called": res.get("function") or res.get("function_called"),
            "arguments": res.get("arguments"),
            "summary": res.get("summary", ""),
            "model_used": res.get("model_used")
        }
    elif res.get("status") == "direct_response":
        return {
            "status": "no_function_call",
            "function": None,
            "function_called": None,
            "arguments": {},
            "summary": res.get("summary", ""),
            "response_message": res.get("final_response"),
            "model_used": res.get("model_used")
        }
    return res


def get_llm_tool_decision(
    message: str,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    current_state: Optional[Dict[str, Any]] = None,
    state_history: Optional[List[Dict[str, Any]]] = None,
    preferred_model: Optional[str] = None
) -> Dict[str, Any]:
    """Inspects LLM function decision and arguments for test verification without executing the flow."""
    res = evaluate_customer_message(message, conversation_history, current_state, state_history, preferred_model)
    out = {
        "function": res.get("function") or "none",
        "action": res.get("function") or "none",
        "arguments": res.get("arguments") or {},
        "summary": res.get("summary") or "",
        "model_used": res.get("model_used"),
        "status": res.get("status")
    }
    if res.get("error"):
        out["error"] = res["error"]
    return out


decide_function_call = evaluate_customer_message

