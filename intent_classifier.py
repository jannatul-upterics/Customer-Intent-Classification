import os
import sys
import json
import re
import time
import requests
from typing import Optional, Dict, Any, List

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Required Fields Schema
# ---------------------------------------------------------------------------
REQUIRED_FIELDS = ["intent", "party_size", "date", "time", "food_preference"]

# Canonical dietary mappings
FOOD_SYNONYMS = {
    "peanut allergy": "nut-free",
    "peanut allergies": "nut-free",
    "peanut-free": "nut-free",
    "peanut": "nut-free",
    "nut allergy": "nut-free",
    "tree nut allergy": "nut-free",
    "peanuts": "nut-free",
    "nuts": "nut-free",
    "celiac": "gluten-free",
    "celiac disease": "gluten-free",
    "lactose": "dairy-free",
    "lactose intolerant": "dairy-free",
    "lactose-free": "dairy-free",
}

# ---------------------------------------------------------------------------
# Improved Extraction System Prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are an expert Natural Language Understanding (NLU) extraction engine specialized in restaurant reservation systems. Your task is to analyze customer messages, identify their primary intent, and extract structured booking parameters.

You must extract exactly the following five fields:
1. "intent": The customer's primary objective ("booking", "inquiry", "cancellation", "modification"). If the customer is requesting, initiating, or asking to reserve a table, classify as "booking". If asking questions without booking, classify as "inquiry". If cancelling, classify as "cancellation". If modifying an existing reservation, classify as "modification".
2. "party_size": Total number of dining guests as an integer. Accurately interpret phrases such as "five people", "table for 5", "table for five", "party of five", "party of 5", "five of us", "a couple" (2), "just myself" (1), "two people" (2), etc. If the guest count is not explicitly mentioned, ambiguous, or non-positive (e.g. 0), set to null. Never guess or assume party size.
3. "date": The requested booking date or day as a string:
   - Preserve relative date expressions by extracting the canonical weekday name, stripping leading conversational modifiers: "this Saturday" -> "Saturday", "on Friday" -> "Friday", "this Sunday" -> "Sunday".
   - Use relative day keywords when stated: "today", "tonight", "tomorrow".
   - If the date is an indefinite multi-day period ("next weekend", "sometime this week"), an impossible calendar date ("February 30th", "February 31st"), or omitted, set to null.
4. "time": The requested reservation time standardized strictly into 24-hour "HH:MM" format. Convert common time formats such as "8 PM", "8:00 in the evening", "8:00 PM", "20:00" -> "20:00", "7:30 PM", "7:30 in the evening" -> "19:30", "1:00 PM", "1 PM" -> "13:00", "noon", "12 PM" -> "12:00", "10:30 AM" -> "10:30", "9 AM" -> "09:00". Approximate times anchored to an hour ("around 8 PM", "8-ish") resolve to that hour ("20:00"). If time is omitted or given as a wide multi-hour window ("between 6 and 9 PM", "evening"), set to null.
5. "food_preference": An array of dietary requirements, allergies, or culinary preferences explicitly mentioned by the customer (e.g., "vegetarian", "vegan", "halal", "kosher", "gluten-free", "dairy-free", "nut-free", "pescatarian"). Standardize allergen terms into canonical tags:
   - Peanut / tree nut allergy -> "nut-free"
   - Celiac / gluten allergy -> "gluten-free"
   - Lactose intolerant / dairy allergy -> "dairy-free"
   If no dietary preferences are explicitly stated, return an empty array []. Never guess food preferences.

Strict Operational & Anti-Hallucination Rules:
- Extract ONLY information explicitly mentioned by the customer. Never guess, assume, or invent details.
- Handle multiple pieces of information packed into a single sentence (e.g., "I'd like a table for five this Saturday at 8 PM. One person is vegetarian." -> party_size: 5, date: "Saturday", time: "20:00", food_preference: ["vegetarian"]).
- Handle natural conversational wording, informal slang ("me and 7 buddies" -> 8), and typos ("tbl for 3 peopel tommorow" -> party_size: 3, date: "tomorrow").
- Distinguish party size numbers from times or dietary headcounts (e.g. in "table for five at 8 PM, one person is vegetarian", party_size is 5, not 1 or 8).
- For mid-sentence self-corrections ("table for 4... make that 6"), use the latest revised value.
- All five fields ("intent", "party_size", "date", "time", "food_preference") must always be present in the output JSON. Never change field names or omit keys.
- Return strictly valid raw JSON only. Do not wrap in markdown code blocks (no ```json). Do not include any explanations, greetings, or extra text.

Examples:

Customer Input: "I'd like a table for five this Saturday at 8 PM. One person is vegetarian."
Output:
{"intent": "booking", "party_size": 5, "date": "Saturday", "time": "20:00", "food_preference": ["vegetarian"]}

Customer Input: "Can we reserve a table for 5 people this Saturday at 8:00 in the evening? Two of us are vegan."
Output:
{"intent": "booking", "party_size": 5, "date": "Saturday", "time": "20:00", "food_preference": ["vegan"]}

Customer Input: "Party of five for tomorrow at 20:00, no dietary requirements."
Output:
{"intent": "booking", "party_size": 5, "date": "tomorrow", "time": "20:00", "food_preference": []}

Customer Input: "Can we reserve a booth for four this Friday evening? We'll drop by sometime between 6 and 9 PM."
Output:
{"intent": "booking", "party_size": 4, "date": "Friday", "time": null, "food_preference": []}

Customer Input: "I'd like a table for five sometime next weekend at 7 PM. One person is pescatarian."
Output:
{"intent": "booking", "party_size": 5, "date": null, "time": "19:00", "food_preference": ["pescatarian"]}

Customer Input: "Can I book a table for 2 on February 31st at 8 PM? No allergies."
Output:
{"intent": "booking", "party_size": 2, "date": null, "time": "20:00", "food_preference": []}

Customer Input: "Booking for 8 guests on Monday at 12:00 PM. We have one vegan, one celiac gluten-free, and one peanut allergy."
Output:
{"intent": "booking", "party_size": 8, "date": "Monday", "time": "12:00", "food_preference": ["vegan", "gluten-free", "nut-free"]}

Customer Input: "Do you offer vegan options and what time do you close this Saturday?"
Output:
{"intent": "inquiry", "party_size": null, "date": "Saturday", "time": null, "food_preference": ["vegan"]}
"""

# ---------------------------------------------------------------------------
# Dialogue State Tracking (DST) System Prompt
# ---------------------------------------------------------------------------
STATE_TRACKING_SYSTEM_PROMPT = """You are an expert dialogue state tracking (DST) engine specialized in restaurant reservation systems.
Your task is to analyze the Current Conversation State and the latest Customer Message, determine what information the message adds, changes, removes, or indicates about the customer's intent, and return the strictly updated conversation state as raw JSON.

You must output a JSON object containing exactly these five fields:
1. "intent": The customer's primary objective ("booking", "inquiry", "cancellation", "modification"). If creating or continuing a booking, use "booking". If modifying an established reservation, use "modification". If asking questions without booking, use "inquiry". If cancelling, use "cancellation".
2. "party_size": Total number of dining guests as an integer. Accurately interpret phrases like "table for 4", "make it 6", "just 2 of us", "a couple" (2). If unspecified or removed, set to null.
3. "date": The requested booking date or weekday string:
   - Weekday name capitalized: "Saturday", "Friday", etc.
   - Relative day: "today", "tonight", "tomorrow".
   - If removed or not yet specified, set to null.
4. "time": The requested reservation time standardized strictly into 24-hour "HH:MM" format (e.g. "20:00", "19:30", "12:00"). If removed or not yet specified, set to null.
5. "food_preference": An array of canonical dietary requirements or allergies (e.g. ["vegetarian", "vegan", "gluten-free", "dairy-free", "nut-free", "halal", "kosher", "pescatarian"]). If none or if removed, return an empty array [].

Strict Dialogue State Tracking Rules:
1. ONLY update an existing field when the customer explicitly provides a new value for that field.
2. CRITICAL RULE FOR PARTY SIZE & DIETARY REQUIREMENTS:
   - Only update an existing "party_size" when the customer explicitly states a new total guest count (e.g., "Actually, make it 6", "make it 6 people", "party of 5 instead", "can we change to 4 people?").
   - Do NOT infer, calculate, increment, or change "party_size" simply because the customer mentions a colleague, friend, family member, guest, or another person's dietary requirement or allergy (e.g., "my colleague has a severe nut allergy", "and another colleague is vegetarian", "one person is vegan", "my friend can't eat gluten").
   - Adding a dietary requirement MUST update "food_preference" WITHOUT changing "party_size". The party size remains strictly unchanged.
   - If the customer was previously booked for 3 people, and then says "My colleague has a peanut allergy" or "And another colleague is vegetarian", party_size MUST remain 3!
3. Add newly provided information: When a field was null (or empty array) and the customer supplies it, populate it.
4. Replace / update information: When the customer explicitly changes a detail (using words like "actually", "make it 6", "instead", "change that to", "move it to 8 PM", "next Friday"), overwrite the existing value with the newly requested value.
5. Change dietary requirement (Substitution vs Addition): When the customer changes or corrects a dietary requirement (e.g., "Actually, make it vegan", "Instead of vegetarian, make it vegan", "change to gluten-free"), replace the previous requirement so only the new requirement remains. Do NOT keep the previous requirement unless both were explicitly requested (e.g., "we also have a vegan" or "both vegetarian and vegan").
6. Change multiple booking details: When the customer updates multiple parameters at once (e.g., "Actually, make it 6 people at 8 PM"), update all specified fields simultaneously (party_size to 6, time to "20:00") while retaining any other fields already collected.
7. Remove information: When the customer explicitly cancels, removes, or negates a requirement (e.g. "actually no dietary requirements", "no allergies", "forget the dietary restrictions", "we don't need vegetarian", "cancel the date", "never mind the time", "any time is fine"), reset that field to null (or [] for food_preference).
8. Changing customer intent: If the customer changes their goal completely (e.g., "Actually, I don't want to book anymore. Can you tell me the restaurant's opening hours?" -> intent="inquiry"; "please cancel our table" -> intent="cancellation"), update the "intent" field to match their new intention.
9. Preserve all previously collected information unless the customer explicitly changes or removes it. Do not make assumptions or infer information that the customer did not state.
10. Return strictly valid raw JSON only. Do not wrap in markdown code blocks. No commentary.

Examples:

Current State: {"intent": "booking", "party_size": null, "date": null, "time": null, "food_preference": []}
Customer Message: "I'd like a table for 4."
Updated State: {"intent": "booking", "party_size": 4, "date": null, "time": null, "food_preference": []}

Current State: {"intent": "booking", "party_size": 4, "date": null, "time": null, "food_preference": []}
Customer Message: "This Saturday at 8 PM."
Updated State: {"intent": "booking", "party_size": 4, "date": "Saturday", "time": "20:00", "food_preference": []}

Current State: {"intent": "booking", "party_size": 4, "date": "Saturday", "time": "20:00", "food_preference": []}
Customer Message: "Actually, make it 6."
Updated State: {"intent": "booking", "party_size": 6, "date": "Saturday", "time": "20:00", "food_preference": []}

Current State: {"intent": "booking", "party_size": 3, "date": "Sunday", "time": "13:00", "food_preference": []}
Customer Message: "My colleague has a severe peanut allergy."
Updated State: {"intent": "booking", "party_size": 3, "date": "Sunday", "time": "13:00", "food_preference": ["nut-free"]}

Current State: {"intent": "booking", "party_size": 3, "date": "Sunday", "time": "13:00", "food_preference": ["nut-free"]}
Customer Message: "And another colleague is vegetarian."
Updated State: {"intent": "booking", "party_size": 3, "date": "Sunday", "time": "13:00", "food_preference": ["nut-free", "vegetarian"]}

Current State: {"intent": "booking", "party_size": 4, "date": null, "time": "19:00", "food_preference": []}
Customer Message: "Actually, make it 6 people at 8 PM."
Updated State: {"intent": "booking", "party_size": 6, "date": null, "time": "20:00", "food_preference": []}

Current State: {"intent": "booking", "party_size": null, "date": null, "time": null, "food_preference": ["vegetarian"]}
Customer Message: "Actually, make it vegan."
Updated State: {"intent": "booking", "party_size": null, "date": null, "time": null, "food_preference": ["vegan"]}

Current State: {"intent": "booking", "party_size": 6, "date": "Saturday", "time": "20:00", "food_preference": ["vegetarian"]}
Customer Message: "Actually, no dietary requirements."
Updated State: {"intent": "booking", "party_size": 6, "date": "Saturday", "time": "20:00", "food_preference": []}

Current State: {"intent": "booking", "party_size": 4, "date": null, "time": null, "food_preference": []}
Customer Message: "Actually, I don't want to book anymore. Can you tell me the restaurant's opening hours?"
Updated State: {"intent": "inquiry", "party_size": 4, "date": null, "time": null, "food_preference": []}

Current State: {"intent": "booking", "party_size": 6, "date": "Saturday", "time": "20:00", "food_preference": []}
Customer Message: "Please cancel our reservation."
Updated State: {"intent": "cancellation", "party_size": 6, "date": "Saturday", "time": "20:00", "food_preference": []}
"""

# ---------------------------------------------------------------------------
# Extraction & Validation Logic
# ---------------------------------------------------------------------------
def extract_booking_info(message: str) -> dict:
    # 1. Resolve API Key configuration
    api_key = os.environ.get("GROQ_API_KEY")

    if not api_key:
        return {
            "error": "GROQ_API_KEY is not set. Please set your Groq key before running:\n"
                     "  In PowerShell: $env:GROQ_API_KEY = 'gsk_your_key_here'\n"
                     "  Or create a .env file with: GROQ_API_KEY=gsk_your_key_here"
        }

    base_url = "https://api.groq.com/openai/v1"
    preferred_model = os.environ.get("LLM_MODEL", "openai/gpt-oss-20b")
    models_to_try = [
        preferred_model,
        "groq/compound-mini",
        "openai/gpt-oss-120b",
        "groq/compound",
        "qwen/qwen3.8-27b",
        "openai/gpt-oss-safeguard-20b",
        "qwen/qwen3.6-27b"
    ]

    # Deduplicate while preserving order
    seen = set()
    models_to_try = [m for m in models_to_try if m and not (m in seen or seen.add(m))]

    last_error = None
    raw_content = None

    # 2. Send request to LLM API (with automatic fallback if model not found)
    for model in models_to_try:
        try:
            response = requests.post(
                f"{base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": f"Customer message:\n\n{message}"}
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.0,
                    "max_tokens": 500
                },
                timeout=30
            )
        except requests.exceptions.RequestException as err:
            return {"error": f"API request failed: Connection error ({err})"}

        if response.status_code == 200:
            try:
                result_data = response.json()
                raw_content = result_data["choices"][0]["message"]["content"]
                break
            except (KeyError, IndexError, json.JSONDecodeError) as err:
                last_error = f"Invalid response structure from API: {err}"
                continue
        else:
            try:
                err_json = response.json()
                err_msg = err_json.get("error", {}).get("message", response.text)
            except Exception:
                err_msg = response.text
            last_error = f"API error ({response.status_code}): {err_msg}"
            if response.status_code in (404, 429):
                time.sleep(1)
                continue
            else:
                return {"error": last_error}

    if raw_content is None:
        return {"error": last_error or "No valid model response received."}

    # 3. Parse JSON response gracefully (handling optional markdown wrapping)
    cleaned_content = raw_content.strip()
    if cleaned_content.startswith("```json"):
        cleaned_content = cleaned_content[7:]
    elif cleaned_content.startswith("```"):
        cleaned_content = cleaned_content[3:]
    if cleaned_content.endswith("```"):
        cleaned_content = cleaned_content[:-3]
    cleaned_content = cleaned_content.strip()

    try:
        data = json.loads(cleaned_content)
    except json.JSONDecodeError:
        match = re.search(r"(\{.*\})", cleaned_content, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
            except json.JSONDecodeError:
                return {"error": "Failed to parse LLM response as JSON."}
        else:
            return {"error": "Failed to parse LLM response as JSON."}

    # 4. Validate that data is a JSON object
    if not isinstance(data, dict):
        return {"error": "LLM response is not a valid JSON object."}

    missing_fields = [field for field in REQUIRED_FIELDS if field not in data]
    if missing_fields:
        return {"error": f"Missing required field(s) in LLM response: {missing_fields}"}

    return normalize_booking_data(data)

def normalize_booking_data(data: dict) -> dict:
    """
    Lightweight validation & strict type enforcement in Python:
    - Normalizes 24-hour time
    - Canonicalizes dietary terms
    - Strips leading weekday modifiers
    - Normalizes integer party size
    """
    if not isinstance(data, dict):
        return {"error": "Expected dict for normalization."}

    # 1. intent: must exist as a string
    intent_val = data.get("intent")
    if intent_val is not None and str(intent_val).strip():
        intent_val = str(intent_val).strip().lower()
    else:
        intent_val = "booking"

    # 2. party_size: must be an integer when provided, or null
    party_size = data.get("party_size")
    if party_size is not None:
        try:
            party_size = int(float(party_size))
            if party_size <= 0:
                party_size = None
        except (ValueError, TypeError):
            party_size = None

    # 3. date: must be a string when provided, or null
    date_val = data.get("date")
    if date_val is not None:
        date_val = str(date_val).strip()
        if not date_val or date_val.lower() in ("null", "none"):
            date_val = None
        else:
            # Strip leading conversational modifier if followed by a day of the week
            match = re.match(r"^(?:this|on|next)\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)$", date_val, re.IGNORECASE)
            if match:
                date_val = match.group(1).capitalize()
            elif date_val.lower() in ("next weekend", "this weekend", "weekend", "next week", "sometime next week"):
                date_val = None
            elif re.search(r"\bfeb(?:ruary)?\s*(?:30|31)(?:st|th)?\b", date_val, re.IGNORECASE):
                date_val = None

    # 4. time: must follow 24-hour HH:MM format when provided, or null
    time_val = data.get("time")
    if time_val is not None:
        time_val = str(time_val).strip()
        if not re.match(r"^(?:[01]\d|2[0-3]):[0-5]\d$", time_val):
            # Lightweight fallback: normalize 12-hour conversational time (e.g. "8 PM", "8:30 PM", "8:00 in the evening")
            match_12h = re.match(r"^(\d{1,2})(?::(\d{2}))?\s*(?:in the evening|in the afternoon|in the morning)?\s*(am|pm)?$", time_val, re.IGNORECASE)
            if match_12h:
                h = int(match_12h.group(1))
                m = int(match_12h.group(2) or 0)
                meridiem = (match_12h.group(3) or "").lower()
                is_evening = "evening" in time_val.lower() or "pm" in time_val.lower()
                if (is_evening or meridiem == "pm") and h < 12:
                    h += 12
                elif (not is_evening and meridiem == "am") and h == 12:
                    h = 0
                time_val = f"{h:02d}:{m:02d}"
            else:
                time_val = None

    # 5. food_preference: must be a list of strings
    raw_food = data.get("food_preference")
    if isinstance(raw_food, list):
        items = [str(item).strip() for item in raw_food if item and str(item).strip()]
    elif isinstance(raw_food, str):
        items = [raw_food.strip()] if raw_food.strip() else []
    else:
        items = []

    # Apply synonym normalization to canonical tags
    normalized_food = []
    for item in items:
        canonical = FOOD_SYNONYMS.get(item.lower(), item.lower())
        if canonical not in normalized_food:
            normalized_food.append(canonical)

    return {
        "intent": intent_val,
        "party_size": party_size,
        "date": date_val,
        "time": time_val,
        "food_preference": normalized_food
    }

def update_booking_state_with_llm(current_state: Optional[dict], message: str) -> dict:
    """
    Dialogue State Tracking with LLM:
    Takes the Current Conversation State and the latest Customer Message,
    prompts the LLM to determine additions, updates, removals, or intent shifts,
    and returns the updated state dictionary.
    """
    if not message or not str(message).strip():
        return current_state or {
            "intent": "booking",
            "party_size": None,
            "date": None,
            "time": None,
            "food_preference": []
        }

    base_state = {
        "intent": current_state.get("intent", "booking") if current_state else "booking",
        "party_size": current_state.get("party_size") if current_state else None,
        "date": current_state.get("date") if current_state else None,
        "time": current_state.get("time") if current_state else None,
        "food_preference": list(current_state.get("food_preference", [])) if current_state else []
    }

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return {
            "error": "GROQ_API_KEY is not set. Please set your Groq key before running:\n"
                     "  In PowerShell: $env:GROQ_API_KEY = 'gsk_your_key_here'\n"
                     "  Or create a .env file with: GROQ_API_KEY=gsk_your_key_here"
        }
    api_key = api_key.strip()

    base_url = "https://api.groq.com/openai/v1"
    preferred_model = os.environ.get("LLM_MODEL", "openai/gpt-oss-20b")
    models_to_try = [
        preferred_model,
        "groq/compound-mini",
        "openai/gpt-oss-120b",
        "groq/compound",
        "qwen/qwen3.8-27b",
        "openai/gpt-oss-safeguard-20b",
        "qwen/qwen3.6-27b"
    ]

    seen = set()
    models_to_try = [m for m in models_to_try if m and not (m in seen or seen.add(m))]

    user_content = (
        f"Current Conversation State:\n{json.dumps(base_state, indent=2)}\n\n"
        f"Customer Message:\n\"{message}\""
    )

    last_error = None
    raw_content = None

    for model in models_to_try:
        try:
            response = requests.post(
                f"{base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": STATE_TRACKING_SYSTEM_PROMPT},
                        {"role": "user", "content": user_content}
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.0,
                    "max_tokens": 600
                },
                timeout=30
            )
        except requests.exceptions.RequestException as err:
            return {"error": f"API request failed: Connection error ({err})"}

        if response.status_code == 200:
            try:
                result_data = response.json()
                raw_content = result_data["choices"][0]["message"]["content"]
                if raw_content and raw_content.strip():
                    break
            except (KeyError, IndexError, json.JSONDecodeError) as err:
                last_error = f"Invalid response structure from API: {err}"
                continue
        else:
            try:
                err_json = response.json()
                err_msg = err_json.get("error", {}).get("message", response.text)
            except Exception:
                err_msg = response.text
            last_error = f"API error ({response.status_code}): {err_msg}"
            if response.status_code == 429:
                time.sleep(2.5)
                continue
            elif response.status_code in (400, 404):
                time.sleep(0.5)
                continue
            else:
                return {"error": last_error}

    if raw_content is None:
        return {"error": last_error or "No valid model response received."}

    cleaned_content = raw_content.strip()
    if cleaned_content.startswith("```json"):
        cleaned_content = cleaned_content[7:]
    elif cleaned_content.startswith("```"):
        cleaned_content = cleaned_content[3:]
    if cleaned_content.endswith("```"):
        cleaned_content = cleaned_content[:-3]
    cleaned_content = cleaned_content.strip()

    try:
        data = json.loads(cleaned_content)
    except json.JSONDecodeError:
        match = re.search(r"(\{.*\})", cleaned_content, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
            except json.JSONDecodeError:
                return {"error": "Failed to parse LLM response as JSON."}
        else:
            return {"error": "Failed to parse LLM response as JSON."}

    if not isinstance(data, dict):
        return {"error": "LLM response is not a valid JSON object."}

    missing_fields = [field for field in REQUIRED_FIELDS if field not in data]
    if missing_fields:
        return {"error": f"Missing required field(s) in LLM response: {missing_fields}"}

    normalized = normalize_booking_data(data)

    # Party Size Preservation Rule:
    # 1. Only update an existing field when the customer explicitly provides a new value for that field.
    # 2. Never infer a change in party_size simply because the customer mentions a colleague,
    #    friend, family member, or another person's dietary requirement.
    # 3. Adding a dietary requirement must update food_preference without changing party_size.
    if base_state.get("party_size") is not None and normalized.get("party_size") != base_state.get("party_size"):
        msg_lower = message.lower()
        explicit_party_patterns = [
            r"\b(?:make\s+it|make\s+that)\s+(?:\w+\s+)*(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\b",
            r"\b(?:change|switch|update)(?:\s+\w+)*\s+to\s+(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\b",
            r"\b(?:table|booth|party|reservation|seats?)\s+for\s+(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\b",
            r"\b(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+(?:people|guests|persons|diners|seats|of\s+us)\b",
            r"\b(?:add|plus)\s+(?:\d+|one|two|three|four|five|six)\s+(?:more\s+)?(?:people|guests|persons|diners|seats)?\b",
            r"\b(?:just|only)\s+(?:\d+|one|two|three|four|five|six)\s*(?:people|guests|of\s+us)?\b"
        ]
        has_explicit_party_change = any(re.search(p, msg_lower) for p in explicit_party_patterns)
        is_dietary_mention = bool(re.search(r"\b(?:colleague|friend|partner|spouse|guest|someone|person|one)\b.*\b(?:vegetarian|vegan|allergy|allergic|gluten|celiac|nut|peanut|dairy|lactose|halal|kosher|pescatarian|diet)\b", msg_lower))

        if not has_explicit_party_change or (is_dietary_mention and not re.search(r"\b(?:make\s+it|change\s+to|switch\s+to)\s+\d+\b", msg_lower)):
            normalized["party_size"] = base_state["party_size"]

    return normalized

# Backward compatibility alias
classify_intent = extract_booking_info

# Export state management class
from state_manager import BookingState

# ---------------------------------------------------------------------------
# Main CLI Entrypoint: Strictly Output Machine-Readable JSON
# ---------------------------------------------------------------------------
def main():
    if "--session" in sys.argv or "-s" in sys.argv:
        print("Starting interactive restaurant booking session. Type 'exit' to quit, 'reset' to clear state.\n")
        session = BookingState()
        while True:
            try:
                msg = input("Customer: ").strip()
            except (KeyboardInterrupt, EOFError):
                break
            if not msg:
                continue
            if msg.lower() in ("exit", "quit", "q"):
                break
            if msg.lower() == "reset":
                session.reset()
                print("State reset to initial defaults.")
                continue
            state = session.process_message(msg)
            print("State:")
            print(json.dumps(state, indent=4))
            print()
        return

    try:
        customer_message = input().strip()
    except (KeyboardInterrupt, EOFError):
        return

    if not customer_message:
        print(json.dumps({"error": "Customer message cannot be empty."}))
        sys.exit(1)

    result = extract_booking_info(customer_message)
    print(json.dumps(result, indent=4))

if __name__ == "__main__":
    main()

