import os
import sys
import json
import re
import time
import requests

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
1. "intent": The customer's primary objective ("booking", "inquiry", "cancellation", "modification"). If the user is requesting or asking to reserve a table, set this to "booking". If asking questions without reserving, set to "inquiry". If cancelling, set to "cancellation". If modifying an existing reservation, set to "modification".
2. "party_size": The total number of guests as an integer. Convert word numbers to digits (e.g., "five" -> 5, "a couple" -> 2, "myself" -> 1). If unspecified, ambiguous, or zero/negative, set to null.
3. "date": The target reservation day or date normalized:
   - Extract canonical single day names, removing leading modifiers (e.g., "this Friday" -> "Friday", "on Saturday" -> "Saturday", "this Sunday" -> "Sunday").
   - Relative day terms without a specific weekday: "today", "tonight", "tomorrow".
   - Indefinite multi-day ranges (e.g., "next weekend", "sometime this week", "next week"): must be set to null.
   - Non-existent / impossible calendar dates (e.g., "February 30th", "February 31st"): must be set to null.
   - If unspecified or missing, set to null.
4. "time": The reservation time standardized strictly into 24-hour "HH:MM" format (e.g., "8 PM" -> "20:00", "around 8 PM" -> "20:00", "1:30 PM" -> "13:30", "9 AM" -> "09:00", "noon" -> "12:00", "19:30" -> "19:30"). Approximate times anchored to a specific hour (e.g., "around 8 PM") should resolve to that hour ("20:00"). Only wide multi-hour intervals (e.g. "between 6 and 9 PM", "evening") or unspecified times should be set to null.
5. "food_preference": An array of standardized dietary restriction and allergy tags mentioned in the message, even for general inquiries. Map terms to canonical tags:
   - Peanut / tree nut allergy -> "nut-free"
   - Celiac / gluten allergy -> "gluten-free"
   - Lactose intolerant / dairy allergy -> "dairy-free"
   - Vegetarian -> "vegetarian"
   - Vegan -> "vegan"
   - Halal -> "halal"
   - Kosher -> "kosher"
   - Pescatarian -> "pescatarian"
   If no dietary preferences are mentioned, this must be an empty array [].

Strict Extraction and Normalization Rules:
- All five fields ("intent", "party_size", "date", "time", "food_preference") must always be present in the output JSON.
- Never omit a key. Use null when an entity cannot be determined, except for food_preference which must always be an array ([] if none).
- Distinguish between numbers denoting party size and numbers denoting time or dietary counts (e.g., in "table for five at 8 PM, one person is vegetarian", party_size is 5, not 1 or 8).
- In case of inline user corrections, prioritize the latest corrected value.
- Robustly handle natural conversational variations, colloquial phrasing, informal slang, and minor typos or grammatical errors.
- Never invent information not provided in the customer message.
- Return raw JSON only. Do not enclose the output in markdown code fences. Do not include any explanations, greetings, or extra text.

Examples:

Customer Input: "I'd like a table for five this Saturday at 8 PM. One person is vegetarian."
Output:
{"intent": "booking", "party_size": 5, "date": "Saturday", "time": "20:00", "food_preference": ["vegetarian"]}

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
    models_to_try = [preferred_model, "groq/compound", "qwen/qwen3.6-27b"]

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
                    "temperature": 0.0
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

    # 5. Strict type enforcement and sanitization
    # intent: string
    intent_val = data.get("intent")
    intent_val = str(intent_val).strip() if intent_val else "booking"

    # party_size: integer or null
    party_size = data.get("party_size")
    if party_size is not None:
        try:
            party_size = int(party_size)
            if party_size <= 0:
                party_size = None
        except (ValueError, TypeError):
            party_size = None

    # date: string or null
    date_val = data.get("date")
    if date_val is not None:
        date_val = str(date_val).strip()
        if not date_val or date_val.lower() in ("null", "none"):
            date_val = None
        else:
            # Strip leading modifier if followed by a day of the week
            match = re.match(r"^(?:this|on|next)\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)$", date_val, re.IGNORECASE)
            if match:
                date_val = match.group(1).capitalize()
            elif date_val.lower() in ("next weekend", "this weekend", "weekend", "next week", "sometime next week"):
                date_val = None
            elif re.search(r"\bfeb(?:ruary)?\s*(?:30|31)(?:st|th)?\b", date_val, re.IGNORECASE):
                date_val = None

    # time: string in 24-hour HH:MM format or null
    time_val = data.get("time")
    if time_val is not None:
        time_val = str(time_val).strip()
        if not re.match(r"^(?:[01]\d|2[0-3]):[0-5]\d$", time_val):
            time_val = None

    # food_preference: always an array of standardized strings
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

# Backward compatibility alias
classify_intent = extract_booking_info

# ---------------------------------------------------------------------------
# Main CLI Entrypoint: Strictly Output Machine-Readable JSON
# ---------------------------------------------------------------------------
def main():
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
