import os
import sys
import json
import re
import time
import datetime
from datetime import timedelta
from typing import Optional, Dict, Any, List
import requests
from dateutil import parser as date_parser

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Required Fields Schema
# ---------------------------------------------------------------------------
REQUIRED_FIELDS = ["intent", "party_size", "date", "time"]

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
    "vegetarian": "vegetarian",
    "vegan": "vegan",
    "pescatarian": "pescatarian",
    "halal": "halal",
    "kosher": "kosher"
}

# ---------------------------------------------------------------------------
# Calendar Reference & Date Resolution Helpers
# ---------------------------------------------------------------------------
def build_reference_calendar(base_date: Optional[datetime.date] = None) -> str:
    """
    Generates dynamic calendar lookup reference anchored to base_date (defaults to today).
    Provides exact date mappings for weekdays, 'this <weekday>', 'next <weekday>',
    'tomorrow', and 'day after tomorrow' to guide LLM extraction and avoid date math errors.
    """
    if base_date is None:
        base_date = datetime.date.today()
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    current_wd = base_date.weekday()
    current_week_start = base_date - timedelta(days=current_wd)
    next_week_start = current_week_start + timedelta(days=7)

    lines = [f"Today's reference date: {base_date.strftime('%A, %Y-%m-%d')}."]
    lines.append("Calendar Reference for Date Resolution:")
    lines.append("Current week:")
    for i, d in enumerate(days):
        dt = current_week_start + timedelta(days=i)
        tag = " (today)" if i == current_wd else ""
        lines.append(f'  - "this {d}": {dt.isoformat()}{tag}')
    lines.append("Following week:")
    for i, d in enumerate(days):
        dt = next_week_start + timedelta(days=i)
        lines.append(f'  - "next {d}": {dt.isoformat()}')
    lines.append("Next upcoming weekdays (plain day names):")
    for i, d in enumerate(days):
        offset = (i - current_wd) % 7
        if offset == 0:
            offset = 7
        dt = base_date + timedelta(days=offset)
        lines.append(f'  - "{d}": {dt.isoformat()}')
    lines.append(f'  - "tomorrow": {(base_date + timedelta(days=1)).isoformat()}')
    lines.append(f'  - "day after tomorrow": {(base_date + timedelta(days=2)).isoformat()}')
    return "\n".join(lines)

DATE_INDICATOR_PATTERN = re.compile(
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?|\d{1,4}[/\-\.]\d{1,2}[/\-\.]\d{1,4}|\d{1,2}(?:st|nd|rd|th)?)",
    re.IGNORECASE
)

def resolve_calendar_date(raw_date: Optional[str], base_date: Optional[datetime.date] = None) -> Optional[str]:
    """
    Converts relative weekday expressions, relative day keywords, and explicit date strings
    into a standardized calendar date string strictly formatted as 'YYYY-MM-DD'.
    
    Rules:
    - Anchored dynamically to base_date (defaults to datetime.date.today()).
    - Weekday expressions:
      * 'Monday' / '<weekday>' -> next upcoming occurrence of that weekday.
      * 'this Monday' / 'this <weekday>' -> that weekday of the current/relevant week.
      * 'next Monday' / 'next <weekday>' -> that weekday of the following week.
    - Relative day terms:
      * 'today', 'tonight' -> base_date
      * 'tomorrow' -> base_date + 1 day
      * 'day after tomorrow', 'the day after tomorrow' -> base_date + 2 days
    - Explicit dates:
      * Standardized to 'YYYY-MM-DD' (e.g. 'September 25' -> '2026-09-25').
    - Vague expressions ('this weekend', 'next weekend') or impossible dates ('February 31st') -> None.
    - Weekday names alone are never returned.
    """
    if raw_date is None:
        return None
    raw_date = str(raw_date).strip()
    if not raw_date or raw_date.lower() in ("null", "none"):
        return None

    if base_date is None:
        base_date = datetime.date.today()

    cleaned = raw_date.lower()

    # Reject indefinite multi-day periods or explicit impossibilities
    if cleaned in ("this weekend", "next weekend", "weekend", "next week", "sometime next week", "sometime this week", "any day", "any date"):
        return None
    if re.search(r"\bfeb(?:ruary)?\s*(?:30|31)(?:st|th)?\b", cleaned):
        return None
    if re.search(r"\b(?:april|apr|june|jun|september|sep|sept|november|nov)\s*31(?:st)?\b", cleaned):
        return None

    # Check if already ISO YYYY-MM-DD
    if re.match(r"^\d{4}-\d{2}-\d{2}$", raw_date):
        try:
            return datetime.date.fromisoformat(raw_date).isoformat()
        except ValueError:
            return None

    # Relative days
    if cleaned in ("today", "tonight"):
        return base_date.isoformat()
    if cleaned == "tomorrow":
        return (base_date + timedelta(days=1)).isoformat()
    if cleaned in ("day after tomorrow", "the day after tomorrow"):
        return (base_date + timedelta(days=2)).isoformat()

    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    day_map = {d: i for i, d in enumerate(days)}
    current_wd = base_date.weekday()
    current_week_start = base_date - timedelta(days=current_wd)

    # Clean potential trailing time expressions (e.g. 'Saturday at 8 PM' -> 'Saturday')
    cleaned_date_only = re.sub(r"\s+at\s+.*$", "", cleaned).strip()

    # 'this <weekday>'
    m_this = re.match(r"^this\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)$", cleaned_date_only)
    if m_this:
        target_wd = day_map[m_this.group(1)]
        return (current_week_start + timedelta(days=target_wd)).isoformat()

    # 'next <weekday>'
    m_next = re.match(r"^next\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)$", cleaned_date_only)
    if m_next:
        target_wd = day_map[m_next.group(1)]
        return (current_week_start + timedelta(days=7 + target_wd)).isoformat()

    # Plain '<weekday>' or 'on <weekday>' or 'for <weekday>'
    m_plain = re.match(r"^(?:on\s+|for\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)$", cleaned_date_only)
    if m_plain:
        target_wd = day_map[m_plain.group(1)]
        offset = (target_wd - current_wd) % 7
        if offset == 0:
            offset = 7
        return (base_date + timedelta(days=offset)).isoformat()

    # Explicit date parsing via dateutil
    if DATE_INDICATOR_PATTERN.search(cleaned_date_only):
        try:
            default_dt = datetime.datetime(base_date.year, base_date.month, base_date.day)
            parsed_dt = date_parser.parse(raw_date, default=default_dt)
            return parsed_dt.date().isoformat()
        except Exception:
            pass

    return None

# ---------------------------------------------------------------------------
# Improved Extraction System Prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are an expert Natural Language Understanding (NLU) extraction engine specialized in restaurant reservation systems. Your task is to analyze customer messages, identify their primary intent, and extract structured booking parameters.

You must extract the following primary fields:
1. "intent": The customer's primary objective ("booking", "inquiry", "cancellation", "modification"). If the customer is requesting, initiating, or asking to reserve a table, classify as "booking". If asking questions without booking, classify as "inquiry". If cancelling, classify as "cancellation". If modifying an existing reservation, classify as "modification".
2. "party_size": Total number of dining guests as an integer. Accurately interpret phrases such as "five people", "table for 5", "table for five", "party of five", "party of 5", "five of us", "a couple" (2), "just myself" (1), "two people" (2), etc. If the guest count is not explicitly mentioned, ambiguous, or non-positive (e.g. 0), set to null. Never guess or assume party size.
3. "date": The requested booking date resolved strictly into "YYYY-MM-DD" format.
   CRITICAL DATE EXTRACTION & RESOLUTION RULES:
   - Base the calculation dynamically on today's reference date provided in the message prompt.
   - Do NOT return the weekday name alone (e.g. never return "Monday" or "Saturday"). Always resolve to the exact calendar date in "YYYY-MM-DD".
   - Weekday expressions:
     * "<Weekday>" (e.g. "Monday", "Saturday", "on Friday") -> The next upcoming occurrence of that weekday in "YYYY-MM-DD".
     * "this <Weekday>" (e.g. "this Monday", "this Saturday") -> That weekday of the current/relevant week in "YYYY-MM-DD".
     * "next <Weekday>" (e.g. "next Monday", "next Saturday") -> That weekday of the following week in "YYYY-MM-DD".
   - Relative day terms:
     * "today", "tonight" -> Today's date in "YYYY-MM-DD".
     * "tomorrow" -> Tomorrow's date in "YYYY-MM-DD".
     * "day after tomorrow" -> The date two days from today in "YYYY-MM-DD".
   - Explicit calendar dates:
     * Normalize any explicit date (e.g. "September 25", "25th September", "09/25/2026", "Friday, September 25") into "YYYY-MM-DD" (e.g. "2026-09-25").
     * When a weekday is mentioned alongside an explicit date and they are consistent, use the explicit calendar date.
   - Ambiguous, multi-day, or impossible dates:
     * If the date is an indefinite multi-day period ("this weekend", "next weekend", "sometime this week"), an impossible calendar date ("February 30th", "February 31st"), or omitted, set to null.
4. "time": The requested reservation time standardized strictly into 24-hour "HH:MM" format. Convert common time formats such as "8 PM", "8:00 in the evening", "8:00 PM", "20:00" -> "20:00", "7:30 PM", "7:30 in the evening" -> "19:30", "1:00 PM", "1 PM" -> "13:00", "noon", "12 PM" -> "12:00", "10:30 AM" -> "10:30", "9 AM" -> "09:00". Approximate times anchored to an hour ("around 8 PM", "8-ish") resolve to that hour ("20:00"). If time is omitted or given as a wide multi-hour window ("between 6 and 9 PM", "evening"), set to null.

### Preference Counting & Tracking Rules:
For EVERY preference mentioned in the conversation, determine how many people in the party it applies to. All customer preferences are tracked as JSON objects with exact person counts for each preference:

1. "food_preference": Object tracking dietary requirements, allergies, or culinary preferences explicitly mentioned (e.g. "vegetarian", "vegan", "halal", "kosher", "gluten-free", "dairy-free", "nut-free", "pescatarian").
   - Standardize allergen terms into canonical tags:
     * Peanut / tree nut allergy -> "nut-free"
     * Celiac / gluten allergy -> "gluten-free"
     * Lactose intolerant / dairy allergy -> "dairy-free"
   - When party_size is known and dietary preferences apply to only a subset of the party, track the remainder under "non_vegetarian" (e.g. party_size=5, 1 vegetarian -> {"vegetarian": 1, "non_vegetarian": 4}).
   - When a dietary preference applies to all guests in the party, assign the full party size to that preference (e.g. party_size=5, all vegetarian -> {"vegetarian": 5}). Do NOT include a 0 count for non_vegetarian.
2. "seating_preference": Object tracking table or seating area preferences with exact person counts (e.g. {"window": 2}, {"booth": 4}, {"outdoor": 2}, {"quiet": 1}).
3. "accessibility_requirement": Object tracking accessibility or special equipment needs with exact person counts (e.g. {"wheelchair_access": 1}, {"high_chair": 1}, {"step_free": 2}).
4. "celebration_requirement": Object tracking celebration or event requirements with exact person counts (e.g. {"birthday": 1}, {"anniversary": 2}).
5. Any other preference that can apply to only some or all guests: Object under a descriptive key ending in "_preference" or "_requirement" mapping to exact person counts.

### Important Preference Rules:
1. A preference mentioned for one person must apply ONLY to that person, unless the customer clearly says it applies to everyone.
2. Never assume that a preference mentioned for one guest applies to the entire party. For example, in a party of 6, "Two of us would like window seating" -> "seating_preference": {"window": 2}. Do NOT change this to "window": 6.
3. If the customer gives an exact number, preserve that number.
4. The preference counts should be consistent with the latest party_size. Preference counts can never exceed the total party_size.
5. Exact count interpretations:
   - "one person is vegetarian" -> vegetarian applies to 1 person.
   - "two people need wheelchair access" -> wheelchair accessibility applies to 2 people.
   - "three guests want window seating" -> window seating applies to 3 people.
6. If the customer explicitly says a preference applies to everyone (e.g. "all of us are vegetarian", "we all want window seating"), assign it to the full party size.
7. If the number of people affected by a preference is not specified, do NOT invent a number. Use null for unspecified preference counts (the existing project convention for unspecified counts, e.g. {"window": null}, {"wheelchair_access": null}).
8. If multiple preferences are mentioned, keep their counts separate.
9. If a preference is changed or removed later in the conversation, update the preference count based on the latest customer instruction.
10. If the party size changes, recalculate or validate preference counts against the latest party size. Do not leave impossible counts.

Strict Operational & Anti-Hallucination Rules:
- Extract ONLY information explicitly mentioned by the customer. Never guess, assume, or invent details.
- Handle multiple pieces of information packed into a single sentence.
- Distinguish party size numbers from times or dietary/preference headcounts (e.g. in "table for five at 8 PM, one person is vegetarian", party_size is 5, not 1 or 8).
- For mid-sentence self-corrections ("table for 4... make that 6"), use the latest revised value.
- All primary fields ("intent", "party_size", "date", "time") must always be present in the output JSON. Include applicable preference fields ("food_preference", "seating_preference", "accessibility_requirement", etc.) whenever mentioned.
- Return strictly valid raw JSON only. Do not wrap in markdown code blocks (no ```json). Do not include any explanations, greetings, or extra text.

Examples (assuming reference date Thursday, 2026-09-17):

Example 1 — Food:
Customer Input: "Table for 5. One person is vegetarian."
Output:
{"intent": "booking", "party_size": 5, "date": null, "time": null, "food_preference": {"vegetarian": 1, "non_vegetarian": 4}}

Example 2 — Seating:
Customer Input: "We are 6 people. Two of us would like window seating."
Output:
{"intent": "booking", "party_size": 6, "date": null, "time": null, "seating_preference": {"window": 2}}

Example 3 — Accessibility:
Customer Input: "There will be 5 of us, but one guest uses a wheelchair."
Output:
{"intent": "booking", "party_size": 5, "date": null, "time": null, "accessibility_requirement": {"wheelchair_access": 1}}

Example 4 — Multiple preferences:
Customer Input: "We are 6 people. Two are vegetarian, one needs wheelchair access, and three would prefer a window table."
Output:
{"intent": "booking", "party_size": 6, "date": null, "time": null, "food_preference": {"vegetarian": 2, "non_vegetarian": 4}, "accessibility_requirement": {"wheelchair_access": 1}, "seating_preference": {"window": 3}}

Example 5 — Full party food preference & relative date:
Customer Input: "Party of 5 for tomorrow at 20:00, all of us are vegetarian."
Output:
{"intent": "booking", "party_size": 5, "date": "2026-09-18", "time": "20:00", "food_preference": {"vegetarian": 5}}

Example 6 — Weekday date resolution:
Customer Input: "Table for 4 this Friday at 7 PM. Someone needs wheelchair access."
Output:
{"intent": "booking", "party_size": 4, "date": "2026-09-18", "time": "19:00", "accessibility_requirement": {"wheelchair_access": null}}

Example 7 — Weekday date resolution & multiple dietary restrictions:
Customer Input: "Booking for 8 guests on Monday at 12:00 PM. We have one vegan, one celiac gluten-free, and one peanut allergy."
Output:
{"intent": "booking", "party_size": 8, "date": "2026-09-21", "time": "12:00", "food_preference": {"vegan": 1, "gluten-free": 1, "nut-free": 1, "non_vegetarian": 5}}
"""

# ---------------------------------------------------------------------------
# Dialogue State Tracking (DST) System Prompt
# ---------------------------------------------------------------------------
STATE_TRACKING_SYSTEM_PROMPT = """You are an expert dialogue state tracking (DST) engine specialized in restaurant reservation systems.
Your task is to analyze the Current Conversation State and the latest Customer Message, determine what information the message adds, changes, removes, or indicates about the customer's intent, and return the strictly updated conversation state as raw JSON.

Output Fields:
1. "intent": The customer's primary objective ("booking", "inquiry", "cancellation", "modification"). If creating or continuing a booking, use "booking". If modifying an established reservation, use "modification". If asking questions without booking, use "inquiry". If cancelling, use "cancellation".
2. "party_size": Total number of dining guests as an integer. Accurately interpret phrases like "table for 4", "make it 6", "just 2 of us", "a couple" (2). If unspecified or removed, set to null.
3. "date": The requested booking date resolved strictly into "YYYY-MM-DD" format:
   - Base calculation dynamically on today's reference date provided in the message.
   - Never return weekday names alone (e.g. never return "Monday" or "Tuesday"). Always output "YYYY-MM-DD".
   - If the customer changes the date (e.g. "Actually, make that Tuesday"), update "date" to Tuesday's resolved "YYYY-MM-DD" while preserving other booking parameters.
   - If removed or not yet specified, set to null.
4. "time": The requested reservation time standardized strictly into 24-hour "HH:MM" format (e.g. "20:00", "19:30", "12:00"). If removed or not yet specified, set to null.
5. Customer Preferences with Exact Person Counts:
   - "food_preference": Object mapping canonical dietary tags ("vegetarian", "vegan", "gluten-free", "dairy-free", "nut-free", "halal", "kosher", "pescatarian") to exact guest counts.
     * When party_size is known and dietary restrictions apply to only a subset of guests, track the remainder under "non_vegetarian" (e.g. party_size=5, 1 vegetarian -> {"vegetarian": 1, "non_vegetarian": 4}).
     * When a dietary preference applies to all guests, assign the full party size to that preference (e.g. {"vegetarian": 5}).
     * If dietary requirements are explicitly removed or none exist, return an empty object {}.
   - "seating_preference": Object mapping seating requests to guest counts (e.g. {"window": 2}). Never assume a seating preference mentioned for some guests applies to the whole party.
   - "accessibility_requirement": Object mapping accessibility needs to guest counts (e.g. {"wheelchair_access": 1}).
   - "celebration_requirement": Object mapping celebration types to guest counts (e.g. {"birthday": 1}).
   - Any other preference mentioned by the customer.

Strict Dialogue State Tracking & Preference Counting Rules:
1. ONLY update an existing field when the customer explicitly provides a new value for that field.
2. CRITICAL RULE FOR PARTY SIZE & PREFERENCE HEADCOUNTS:
   - Only update "party_size" when the customer explicitly states a new total guest count (e.g., "Actually, make it 6", "make it 6 people", "party of 5 instead", "can we change to 4 people?").
   - Do NOT infer, calculate, increment, or change "party_size" simply because the customer mentions a colleague, friend, family member, guest, or another person's preference (e.g., "one person is vegetarian", "two of us want window seating", "one guest uses a wheelchair").
   - Adding a preference MUST update that preference's object WITHOUT changing "party_size". The party size remains strictly unchanged.
3. PREFERENCE COUNTING & UPDATES:
   - A preference mentioned for one person must apply ONLY to that person, unless the customer clearly says it applies to everyone.
   - Never assume that a preference mentioned for one guest applies to the entire party.
   - If the customer gives an exact number, preserve that number.
   - If the customer explicitly says a preference applies to everyone, assign it to the full party.
   - If the number of people affected by a preference is not specified, do NOT invent a number. Use null for unspecified preference counts.
   - If multiple preferences are mentioned, keep their counts separate.
   - When a preference count is changed or corrected (e.g., "Actually, two people are vegetarian", "Actually, all of us are vegetarian"), update the preference count based on the latest customer instruction.
   - When dietary counts change or party size changes, recalculate "non_vegetarian" = party_size - sum(restrictions). If sum(restrictions) >= party_size, omit "non_vegetarian".
   - If party size changes, recalculate or validate preference counts against the latest party size so that no preference count exceeds the new party size.
4. DATE RESOLUTION & MULTI-TURN UPDATES:
   - Resolve weekday expressions ("Monday", "this Monday", "next Monday", "Saturday", "tomorrow") to calendar dates in "YYYY-MM-DD" based on today's reference date.
   - If the customer changes the date (e.g. "Actually, make that Tuesday"), update only the "date" field to Tuesday's resolved "YYYY-MM-DD" and keep all other fields intact.
5. REMOVAL OF PREFERENCES / FIELDS:
   - When the customer explicitly cancels, removes, or negates a requirement (e.g. "actually no dietary requirements", "no allergies", "forget the dietary restrictions", "we don't need vegetarian", "never mind the window seating", "no wheelchair access needed"), reset that preference object to {} (or remove it).
   - When cancelling date or time, reset that field to null.
6. Changing customer intent: If the customer changes their goal completely (e.g., "Actually, I don't want to book anymore. Can you tell me the restaurant's opening hours?" -> intent="inquiry"; "please cancel our table" -> intent="cancellation"), update the "intent" field to match their new intention.
7. Preserve all previously collected information unless the customer explicitly changes or removes it. Do not make assumptions or infer information that the customer did not state.
8. Return strictly valid raw JSON only. Do not wrap in markdown code blocks. No commentary.

Examples (assuming reference date Thursday, 2026-09-17):

Current State: {"intent": "booking", "party_size": null, "date": null, "time": null}
Customer Message: "I'd like a table for 5."
Updated State: {"intent": "booking", "party_size": 5, "date": null, "time": null}

Current State: {"intent": "booking", "party_size": 5, "date": "2026-09-19", "time": "20:00"}
Customer Message: "One person is vegetarian."
Updated State: {"intent": "booking", "party_size": 5, "date": "2026-09-19", "time": "20:00", "food_preference": {"vegetarian": 1, "non_vegetarian": 4}}

Current State: {"intent": "booking", "party_size": 4, "date": "2026-09-21", "time": "20:00"}
Customer Message: "Actually, make that Tuesday."
Updated State: {"intent": "booking", "party_size": 4, "date": "2026-09-22", "time": "20:00"}

Current State: {"intent": "booking", "party_size": 5, "date": "2026-09-19", "time": "20:00", "food_preference": {"vegetarian": 1, "non_vegetarian": 4}}
Customer Message: "Actually, two people are vegetarian."
Updated State: {"intent": "booking", "party_size": 5, "date": "2026-09-19", "time": "20:00", "food_preference": {"vegetarian": 2, "non_vegetarian": 3}}

Current State: {"intent": "booking", "party_size": 5, "date": "2026-09-19", "time": "20:00", "food_preference": {"vegetarian": 2, "non_vegetarian": 3}}
Customer Message: "Actually, all of us are vegetarian."
Updated State: {"intent": "booking", "party_size": 5, "date": "2026-09-19", "time": "20:00", "food_preference": {"vegetarian": 5}}

Current State: {"intent": "booking", "party_size": 6, "date": "2026-09-18", "time": "19:00"}
Customer Message: "Two of us would like window seating."
Updated State: {"intent": "booking", "party_size": 6, "date": "2026-09-18", "time": "19:00", "seating_preference": {"window": 2}}

Current State: {"intent": "booking", "party_size": 6, "date": "2026-09-18", "time": "19:00", "seating_preference": {"window": 2}}
Customer Message: "Also, one guest uses a wheelchair and two are vegetarian."
Updated State: {"intent": "booking", "party_size": 6, "date": "2026-09-18", "time": "19:00", "food_preference": {"vegetarian": 2, "non_vegetarian": 4}, "accessibility_requirement": {"wheelchair_access": 1}, "seating_preference": {"window": 2}}

Current State: {"intent": "booking", "party_size": 5, "date": "2026-09-19", "time": "20:00", "food_preference": {"vegetarian": 2, "non_vegetarian": 3}}
Customer Message: "Actually, no dietary requirements."
Updated State: {"intent": "booking", "party_size": 5, "date": "2026-09-19", "time": "20:00", "food_preference": {}}
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

    today = datetime.date.today()
    cal_ref = build_reference_calendar(today)

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
                        {"role": "user", "content": f"{cal_ref}\n\nCustomer message:\n\n{message}"}
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

def normalize_booking_data(data: dict, base_date: Optional[datetime.date] = None) -> dict:
    """
    Lightweight validation & strict type enforcement in Python:
    - Normalizes 24-hour time
    - Canonicalizes dietary terms
    - Resolves dates strictly to YYYY-MM-DD format
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

    # 3. date: must be strictly resolved to YYYY-MM-DD when provided, or null
    date_val = data.get("date")
    date_val = resolve_calendar_date(date_val, base_date=base_date)

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

    # 5. Helper to normalize preference dictionaries and validate counts against party size
    def normalize_pref_dict(raw_dict: Any) -> Dict[str, Any]:
        if not isinstance(raw_dict, dict):
            return {}
        normalized = {}
        for k, v in raw_dict.items():
            clean_k = FOOD_SYNONYMS.get(str(k).strip().lower(), str(k).strip().lower())
            if not clean_k:
                continue
            if v is None or str(v).strip().lower() in ("null", "none"):
                val = None
            else:
                try:
                    val = int(float(v))
                    if val < 0:
                        val = None
                    elif party_size is not None and val > party_size:
                        val = party_size  # Rule 10: clamp impossible counts to party size
                except (ValueError, TypeError):
                    val = None
            normalized[clean_k] = val
        return normalized

    result = {
        "intent": intent_val,
        "party_size": party_size,
        "date": date_val,
        "time": time_val
    }

    # 6. Normalize food_preference
    if "food_preference" in data:
        raw_food = data["food_preference"]
        normalized_food = {}
        if isinstance(raw_food, dict):
            normalized_food = normalize_pref_dict(raw_food)
        elif isinstance(raw_food, list):
            # Backward compatibility for list of strings
            for item in raw_food:
                clean_tag = FOOD_SYNONYMS.get(str(item).strip().lower(), str(item).strip().lower())
                if clean_tag:
                    normalized_food[clean_tag] = 1

        # Recalculate/validate food preference consistency with party_size
        if party_size is not None and normalized_food:
            restricted_count = sum(
                v for k, v in normalized_food.items()
                if k != "non_vegetarian" and isinstance(v, int)
            )
            if restricted_count > 0:
                if restricted_count >= party_size:
                    # All guests are accounted for by restrictions; no non_vegetarian remainder
                    normalized_food.pop("non_vegetarian", None)
                else:
                    # Partial restrictions: assign remainder to non_vegetarian
                    normalized_food["non_vegetarian"] = party_size - restricted_count

        result["food_preference"] = normalized_food

    # 7. Normalize other preference categories (seating_preference, accessibility_requirement, etc.)
    for field_name, field_val in data.items():
        if field_name in ("intent", "party_size", "date", "time", "food_preference"):
            continue
        if field_name.endswith("_preference") or field_name.endswith("_requirement") or "preference" in field_name or "requirement" in field_name:
            if isinstance(field_val, dict):
                result[field_name] = normalize_pref_dict(field_val)
            elif isinstance(field_val, str) and field_val.strip():
                result[field_name] = {field_val.strip().lower(): party_size if party_size else 1}

    return result

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
            "time": None
        }

    base_state = {
        "intent": current_state.get("intent", "booking") if current_state else "booking",
        "party_size": current_state.get("party_size") if current_state else None,
        "date": current_state.get("date") if current_state else None,
        "time": current_state.get("time") if current_state else None
    }
    if current_state:
        for k, v in current_state.items():
            if k not in base_state and k not in ("error", "history", "conversation_messages"):
                if isinstance(v, dict):
                    base_state[k] = dict(v)
                elif isinstance(v, list):
                    base_state[k] = list(v)
                else:
                    base_state[k] = v

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

    today = datetime.date.today()
    cal_ref = build_reference_calendar(today)

    user_content = (
        f"{cal_ref}\n\n"
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
    #    friend, family member, or another person's preference/requirement.
    # 3. Adding a preference must update that preference without changing party_size.
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
        is_preference_mention = bool(re.search(r"\b(?:colleague|friend|partner|spouse|guest|someone|person|one|two|three|four|five|six)\b.*\b(?:vegetarian|vegan|allergy|allergic|gluten|celiac|nut|peanut|dairy|lactose|halal|kosher|pescatarian|diet|wheelchair|window|booth|seating|high\s*chair)\b", msg_lower))

        if not has_explicit_party_change or (is_preference_mention and not re.search(r"\b(?:make\s+it|change\s+to|switch\s+to)\s+\d+\b", msg_lower)):
            normalized["party_size"] = base_state["party_size"]
            # Re-normalize to ensure preference counts are consistent with preserved party size
            normalized = normalize_booking_data(normalized)

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

