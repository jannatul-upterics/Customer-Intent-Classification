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

# Standardized dietary category mappings (lowercase snake_case)
FOOD_SYNONYMS = {
    # Vegetarian
    "vegetarian": "vegetarian",
    "veg": "vegetarian",
    "veggie": "vegetarian",
    "vegetarian food": "vegetarian",
    "veg food": "vegetarian",
    "non-meat": "vegetarian",
    "non_meat": "vegetarian",
    "meat-free": "vegetarian",
    "meat_free": "vegetarian",
    "no meat": "vegetarian",
    "no_meat": "vegetarian",
    "meatless": "vegetarian",

    # Vegan
    "vegan": "vegan",
    "plant-based": "vegan",
    "plant based": "vegan",
    "plant_based": "vegan",
    "fully plant-based": "vegan",
    "fully plant based": "vegan",
    "dairy-free and egg-free": "vegan",
    "dairy free and egg free": "vegan",

    # Dairy-free
    "dairy_free": "dairy_free",
    "dairy-free": "dairy_free",
    "dairy free": "dairy_free",
    "no dairy": "dairy_free",
    "no_dairy": "dairy_free",
    "without dairy": "dairy_free",
    "without_dairy": "dairy_free",
    "lactose intolerant": "dairy_free",
    "lactose intolerance": "dairy_free",
    "lactose-free": "dairy_free",
    "lactose free": "dairy_free",
    "lactose": "dairy_free",

    # Gluten-free
    "gluten_free": "gluten_free",
    "gluten-free": "gluten_free",
    "gluten free": "gluten_free",
    "gluten allergy": "gluten_free",
    "gluten_allergy": "gluten_free",
    "allergic to gluten": "gluten_free",
    "no gluten": "gluten_free",
    "no_gluten": "gluten_free",
    "without gluten": "gluten_free",
    "celiac": "gluten_free",
    "celiac disease": "gluten_free",
    "coeliac": "gluten_free",

    # Nut allergy
    "nut_allergy": "nut_allergy",
    "nut allergy": "nut_allergy",
    "nuts allergy": "nut_allergy",
    "allergic to nuts": "nut_allergy",
    "allergic to peanuts": "nut_allergy",
    "peanut allergy": "nut_allergy",
    "peanut allergies": "nut_allergy",
    "tree nut allergy": "nut_allergy",
    "nut-free": "nut_allergy",
    "nut free": "nut_allergy",
    "nut_free": "nut_allergy",
    "peanut-free": "nut_allergy",
    "peanut free": "nut_allergy",
    "peanut": "nut_allergy",
    "peanuts": "nut_allergy",
    "nuts": "nut_allergy",
    "nut": "nut_allergy",

    # Halal & Kosher
    "halal food": "halal",
    "halal": "halal",
    "kosher food": "kosher",
    "kosher": "kosher",

    # Seafood
    "no_seafood": "no_seafood",
    "no seafood": "no_seafood",
    "seafood-free": "no_seafood",
    "seafood free": "no_seafood",
    "seafood_free": "no_seafood",
    "without seafood": "no_seafood",
    "seafood allergy": "no_seafood",
    "pescatarian": "pescatarian",
    "pescetarian": "pescatarian",

    # Non-vegetarian (only when explicitly mentioned)
    "non_vegetarian": "non_vegetarian",
    "non-vegetarian": "non_vegetarian",
    "non vegetarian": "non_vegetarian",
    "non-veg": "non_vegetarian",
    "non veg": "non_vegetarian",
    "non_veg": "non_vegetarian"
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
        dt = base_date + timedelta(days=offset)
        tag = " (today)" if offset == 0 else ""
        lines.append(f'  - "{d}": {dt.isoformat()}{tag}')
    lines.append(f'  - "today": {base_date.isoformat()}')
    lines.append(f'  - "tonight": {base_date.isoformat()}')
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

The output JSON must contain exactly these 6 fields:
1. "intent": The customer's primary objective ("booking", "inquiry", "cancellation", "modification"). If the customer is requesting, initiating, or asking to reserve a table, classify as "booking". If asking questions without booking, classify as "inquiry". If cancelling, classify as "cancellation". If modifying an existing reservation, classify as "modification".
2. "party_size": Total number of dining guests as an integer. Accurately interpret phrases such as "two people", "table for 4", "party of 5", "me and 3 buddies" (4), "a couple" (2), "just myself" (1), "make it 6 people instead" (6). If the guest count is not explicitly mentioned, ambiguous, or non-positive (e.g. 0), set to null. Never guess or assume party size.
3. "date": The requested booking date resolved strictly into "YYYY-MM-DD" format.
   CRITICAL DATE EXTRACTION & RESOLUTION RULES:
   - Base the calculation dynamically on today's reference date provided in the message prompt.
   - Do NOT return the weekday name alone (e.g. never return "Monday" or "Saturday"). Always resolve to the exact calendar date in "YYYY-MM-DD".
   - Weekday expressions:
     * "<Weekday>" (e.g. "Monday", "Saturday", "on Friday") -> If the requested weekday is today, resolve to today's date in "YYYY-MM-DD". Otherwise, resolve to the next upcoming occurrence of that weekday in "YYYY-MM-DD".
     * "this <Weekday>" (e.g. "this Monday", "this Wednesday", "this Saturday") -> Strictly that weekday of the current calendar week (Monday to Sunday) in "YYYY-MM-DD", even if that weekday has already passed earlier this week. Never shift "this <weekday>" into next week.
     * "next <Weekday>" (e.g. "next Monday", "next Saturday") -> That weekday of the following week in "YYYY-MM-DD".
   - Relative day terms:
     * "today", "tonight" -> Today's date in "YYYY-MM-DD".
     * "tomorrow" -> Tomorrow's date in "YYYY-MM-DD".
     * "day after tomorrow" -> The date two days from today in "YYYY-MM-DD".
   - Mid-sentence self-corrections:
     * If the customer corrects a date mid-sentence (e.g. "on Thursday, sorry I meant Friday"), extract and resolve the latest corrected date ("Friday").
   - Explicit calendar dates:
     * Normalize any explicit date (e.g. "September 25", "25th September", "09/25/2026", "Friday, September 25") into "YYYY-MM-DD" (e.g. "2026-09-25").
     * When a weekday is mentioned alongside an explicit date and they are consistent, use the explicit calendar date.
   - Ambiguous, multi-day, or impossible dates:
     * If the date is an indefinite multi-day period ("this weekend", "next weekend", "sometime this week"), an impossible calendar date ("February 30th", "February 31st"), or omitted, set to null.
4. "time": The requested reservation time standardized strictly into 24-hour "HH:MM" format. Convert common time formats such as "8 PM", "8:00 in the evening", "8:00 PM", "20:00" -> "20:00", "7:30 PM", "7:30 in the evening" -> "19:30", "1:00 PM", "1 PM" -> "13:00", "noon", "12 PM" -> "12:00", "10:30 AM" -> "10:30", "9 AM" -> "09:00". Approximate times anchored to an hour ("around 8 PM", "8-ish") resolve to that hour ("20:00"). If time is omitted or given as a wide multi-hour window ("between 6 and 9 PM", "evening"), set to null.
5. "food_preference": Object tracking dietary requirements, allergies, or culinary preferences explicitly mentioned with exact guest counts.
   - Always return "food_preference" in the JSON output. If no food preferences or dietary requirements are mentioned, return an empty object {}.
   - Standardized Preference Categories (lowercase snake_case):
     The "food_preference" field must use standardized preference categories instead of preserving every variation of the customer's wording:
     * "vegetarian":
       Treat the following as the same preference category: "vegetarian", "veg", "veggie", "vegetarian food", "veg food", "non-meat", "meat-free", "no meat", "meatless".
       Normalize all of these to: "vegetarian".
     * "vegan":
       Treat the following as the same preference category: "vegan", "plant-based", "plant based", "fully plant-based", "dairy-free and egg-free" (when the customer clearly means a vegan diet).
       Normalize all of these to: "vegan".
       CRITICAL: Do NOT automatically treat "vegan" and "vegetarian" as the same dietary requirement. They are different dietary restrictions. However, equivalent wording within each category must be normalized to the same category.
     * "dairy_free":
       Normalize "no dairy", "dairy free", "dairy-free", "without dairy", "lactose intolerant", "lactose-free", "lactose free", "lactose" -> "dairy_free".
     * "gluten_free":
       Normalize "no gluten", "gluten free", "gluten-free", "celiac", "celiac disease", "coeliac" -> "gluten_free".
     * "nut_allergy":
       Normalize "nut allergy", "allergic to nuts", "nuts allergy", "peanut allergy", "peanut allergies", "allergic to peanuts", "tree nut allergy", "peanut", "peanuts", "nuts", "nut-free", "peanut-free" -> "nut_allergy".
     * "halal":
       Normalize "halal food", "halal" -> "halal".
     * "kosher":
       Normalize "kosher food", "kosher" -> "kosher".
     * "no_seafood":
       Normalize "no seafood", "seafood-free", "without seafood", "seafood allergy" -> "no_seafood".
     * "pescatarian":
       Normalize "pescatarian", "pescetarian" -> "pescatarian".

   - Food Preference Normalization Rules:
     1. Normalize equivalent words and phrases to one canonical category.
     2. Do not create separate keys for synonyms.
     3. Do not invent a preference that the customer did not explicitly state (e.g. never invent or assume "non_vegetarian" unless explicitly mentioned by the customer).
     4. Do not merge preferences that are related but have different meanings (e.g. vegan and vegetarian must remain distinct).
     5. If the customer explicitly mentions two different dietary requirements, preserve both.
      6. Maintain the existing preference-counting logic:
         - When a dietary preference applies to all guests in the party (e.g. "all of us are vegetarian", "all halal", "everyone is vegan", "all 4 of us"), assign the full party size to that preference (e.g. party_size=2, "all halal" -> {"halal": 2}).
         - Singular references to one person ("someone", "somebody", "one guest", "one person", "one of us", "a guest", "a friend") explicitly denote a count of 1.
      7. If multiple guests have the same normalized preference, combine their counts (e.g. two are veg and one is vegetarian -> {"vegetarian": 3}; one is vegan and another wants plant-based -> {"vegan": 2}).
      8. If the number of guests with a preference is not specified and does not say "all", do not invent a count (use null).
      9. Preserve the distinction between dietary preferences and allergies.
      10. Use lowercase snake_case for all standardized preference keys.
6. "summary": A short, clear, and natural sentence in third person summarizing the customer's request.

Summary Rules:
1. Always include the "summary" field, even when some information is missing.
2. Generate the summary based only on information explicitly provided by the customer.
3. Do not invent or assume missing information.
4. Make the summary short, clear, and natural.
5. Include the important information extracted from the customer's message.
6. If the customer changes previously provided information, the summary should reflect the latest information.
7. If the customer only provides one piece of information, summarize only that information.
8. Keep the summary suitable for a restaurant booking conversation.

Optional Preference Categories (include ONLY if explicitly requested by the customer):
- "seating_preference": Object tracking table or seating area requests with exact person counts (e.g. {"window": 2}, {"quiet": 1}, {"booth": 4}).
- "accessibility_requirement": Object tracking accessibility needs with exact person counts (e.g. {"wheelchair_access": 1}).
- "celebration_requirement": Object tracking celebration requirements with exact person counts (e.g. {"birthday": 1}).

Strict Output Constraints:
- The output JSON must always contain the standard fields:
  "intent", "party_size", "date", "time", "food_preference", and "summary".
- When no seating or accessibility preferences are mentioned, the output must contain exactly those 6 fields.
- If and only if the customer explicitly mentions seating or accessibility preferences, include "seating_preference" or "accessibility_requirement" with exact counts.
- The "summary" must always be a non-empty string and must never be null or omitted.
- Return strictly valid raw JSON only. Do not wrap in markdown code blocks (no ```json). Do not include any explanations, greetings, or extra text.

Examples:

Customer Input: "hi book a table for 2 people"
Output:
{"intent": "booking", "party_size": 2, "date": null, "time": null, "food_preference": {}, "summary": "Customer wants to book a table for 2 people."}

Customer Input: "Book a table for 4 people tomorrow at 8 PM"
Output:
{"intent": "booking", "party_size": 4, "date": "2026-09-22", "time": "20:00", "food_preference": {}, "summary": "Customer wants to book a table for 4 people tomorrow at 8 PM."}

Customer Input: "Make it 6 people instead"
Output:
{"intent": "booking", "party_size": 6, "date": null, "time": null, "food_preference": {}, "summary": "Customer wants a table for 6 people."}

Customer Input: "I need a vegetarian table for 3"
Output:
{"intent": "booking", "party_size": 3, "date": null, "time": null, "food_preference": {"vegetarian": 3}, "summary": "Customer wants to book a table for 3 vegetarian guests."}

Customer Input: "I need a table for 4, two are veg and one is vegetarian."
Output:
{"intent": "booking", "party_size": 4, "date": null, "time": null, "food_preference": {"vegetarian": 3}, "summary": "Customer wants to book a table for 4 people with 3 vegetarian guests."}

Customer Input: "We have 5 people. One is vegan and another wants plant based food."
Output:
{"intent": "booking", "party_size": 5, "date": null, "time": null, "food_preference": {"vegan": 2}, "summary": "Customer wants to book a table for 5 people with 2 vegan guests."}

Customer Input: "We have 4 guests. Two are vegetarian and one is vegan."
Output:
{"intent": "booking", "party_size": 4, "date": null, "time": null, "food_preference": {"vegetarian": 2, "vegan": 1}, "summary": "Customer wants to book a table for 4 guests with 2 vegetarian and 1 vegan guest."}

Customer Input: "One guest has a nut allergy and two guests are gluten free."
Output:
{"intent": "booking", "party_size": null, "date": null, "time": null, "food_preference": {"nut_allergy": 1, "gluten_free": 2}, "summary": "Customer noted 1 guest with a nut allergy and 2 gluten-free guests."}

Customer Input: "Table for 5. One person is vegetarian."
Output:
{"intent": "booking", "party_size": 5, "date": null, "time": null, "food_preference": {"vegetarian": 1}, "summary": "Customer wants to book a table for 5 people with 1 vegetarian guest."}

Customer Input: "Do you offer takeout catering boxes?"
Output:
{"intent": "inquiry", "party_size": null, "date": null, "time": null, "food_preference": {}, "summary": "Customer is inquiring about takeout catering boxes."}

Customer Input: "Please cancel any booking request under my name."
Output:
{"intent": "cancellation", "party_size": null, "date": null, "time": null, "food_preference": {}, "summary": "Customer wants to cancel their reservation."}
"""

# ---------------------------------------------------------------------------
# Dialogue State Tracking (DST) System Prompt
# ---------------------------------------------------------------------------
STATE_TRACKING_SYSTEM_PROMPT = """You are an expert dialogue state tracking (DST) engine specialized in restaurant reservation systems.
Your task is to analyze the Current Conversation State and the latest Customer Message, determine what information the message adds, changes, removes, or indicates about the customer's intent, and return the strictly updated conversation state as raw JSON.

Output Fields:
1. "intent": The customer's primary objective ("booking", "inquiry", "cancellation", "modification").
   - "booking": If creating or continuing a reservation. If the customer asks about table or time availability (e.g. "Is 9:00 PM open?", "Can we do 7:30?", "Is 8 PM available?"), keep intent as "booking" and update the "time" field accordingly!
   - "inquiry": If asking general questions without wanting to book (e.g. "Do you offer takeout catering boxes?", "What are your hours?"). If the customer was previously booking and switches to an inquiry (e.g. "I don't want to book anymore. Do you offer takeout catering boxes?"), update "intent" to "inquiry", BUT PRESERVE all previously established booking parameters ("party_size", "date", "time", "food_preference") in the state!
   - "cancellation": If cancelling a booking (e.g. "Please cancel any booking request under my name", "cancel our reservation"). Update "intent" to "cancellation", BUT PRESERVE all previously established booking parameters ("party_size", "date", "time", "food_preference") in the state!
   - "modification": If modifying an already confirmed reservation.
2. "party_size": Total number of dining guests as an integer. Accurately interpret phrases like "table for 4", "make it 6", "just 2 of us", "a couple" (2), "me and 3 buddies" (4), "make that 10 people" (10), "Dave dropped out so just 3 of us now" (3). If unspecified or removed, set to null.
3. "date": The requested booking date resolved strictly into "YYYY-MM-DD" format:
   - Base calculation dynamically on today's reference date provided in the message.
   - Plain weekdays ("Friday", "Saturday", "Thursday", "Sunday") resolve to the upcoming calendar date YYYY-MM-DD based on today's reference date.
   - "this Wednesday" resolves to Wednesday of the current week (Monday-Sunday).
   - "tomorrow" resolves to tomorrow's YYYY-MM-DD date.
   - "tonight" / "today" resolves to today's YYYY-MM-DD date.
   - Never return weekday names alone. Always output "YYYY-MM-DD".
   - If the customer changes the date (e.g. "Actually, make that Tuesday", "Can we change the date to Friday instead? Same time"), update "date" to the new resolved "YYYY-MM-DD" while preserving other booking parameters.
   - If removed or not yet specified, set to null.
4. "time": The requested reservation time standardized strictly into 24-hour "HH:MM" format (e.g. "20:00", "19:30", "12:00", "21:00", "18:30").
   - If the customer asks about a time (e.g. "Is 9:00 PM open?"), record "time": "21:00".
   - If the customer pushes the time back/forward (e.g. "push the time back to 8:00 PM"), update "time": "20:00".
   - If the customer asks for a relative time adjustment (e.g. "make it an hour earlier instead" when previously at 20:00), update "time": "19:00".
   - If removed or not yet specified, set to null.
5. Customer Preferences with Exact Person Counts:
   - "food_preference": Object mapping canonical dietary tags ("vegetarian", "vegan", "gluten-free", "dairy-free", "nut-free", "halal", "kosher", "pescatarian") to exact guest counts.
     * When party_size is known and dietary restrictions apply to only a subset of guests, track the remainder under "non_vegetarian" (e.g. party_size=5, 1 vegetarian -> {"vegetarian": 1, "non_vegetarian": 4}).
     * When a dietary preference applies to all guests (e.g. "We're both kosher diners", party_size=2), assign the full party size: {"kosher": 2}.
     * When dietary requirements are explicitly removed or none exist, return an empty object {}.
   - "seating_preference": Object mapping seating requests to guest counts (e.g. {"window": 2}).
   - "accessibility_requirement": Object mapping accessibility needs to guest counts (e.g. {"wheelchair_access": 1}).
   - "celebration_requirement": Object mapping celebration types to guest counts (e.g. {"birthday": 1}).
   - Any other preference mentioned by the customer.

Strict Dialogue State Tracking & Preference Counting Rules:
1. ONLY update an existing field when the customer explicitly provides a new value for that field.
2. CRITICAL RULE FOR PARTY SIZE & PREFERENCE HEADCOUNTS:
   - Only update "party_size" when the customer explicitly states a new total guest count (e.g., "Actually, make it 6", "make that 10 people", "party of 5 instead", "just 3 of us now", "two more people want to join. Make that 6").
   - Do NOT infer, calculate, increment, or change "party_size" simply because the customer mentions a colleague, friend, family member, guest, or another person's preference (e.g., "one person is vegetarian", "my colleague has a severe peanut allergy", "and another colleague is vegetarian", "two of our guests are dairy-free"). In all these cases, party_size remains strictly unchanged!
   - Adding a preference MUST update that preference's object WITHOUT changing "party_size".
3. PREFERENCE COUNTING, ADDITION & SUBSTITUTION:
   - Incremental Addition: When customer mentions a dietary requirement (e.g., "My colleague has a severe peanut allergy" -> {"nut-free": 1}), and in the next turn adds another (e.g., "And another colleague is vegetarian"), ACCUMULATE both: {"nut-free": 1, "vegetarian": 1, "non_vegetarian": remainder}.
   - Substitution: When customer changes or replaces a dietary requirement (e.g., "Actually, make it vegan instead of vegetarian" or "Actually, make it vegan"), REPLACE the prior requirement so only the new requirement remains. Do not keep the previous one unless customer explicitly asked for both.
   - Removal: When customer explicitly clears or cancels dietary requirements (e.g., "Actually, scratch that - the dairy-free guests aren't coming anymore, so no dietary requirements for the table" or "Actually, no dietary requirements"), reset "food_preference" to {}.
   - Recalculate "non_vegetarian" = party_size - sum(restrictions). If sum(restrictions) >= party_size, omit "non_vegetarian".
4. DATE & TIME MULTI-TURN UPDATES:
   - If customer changes date ("Can we change the date to Friday instead? Same time"), update "date" to Friday and keep "time".
   - If customer asks availability ("Is 9:00 PM open?"), update "time": "21:00" and keep "intent": "booking".
   - If customer shifts time ("make it an hour earlier"), subtract 1 hour from current time.
5. INTENT TRANSITIONS & STATE RETENTION:
   - If the customer switches their intention to an inquiry ("Actually, we decided to eat at home instead so I don't want to book anymore. Do you offer takeout catering boxes?") or cancellation ("Please cancel any booking request under my name"), update "intent" to "inquiry" or "cancellation" respectively, but DO NOT wipe out previously collected booking details ("party_size", "date", "time", "food_preference")! Preserve them in the returned JSON state.
6. Return strictly valid raw JSON only. Do not wrap in markdown code blocks. No commentary.

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

Current State: {"intent": "booking", "party_size": 2, "date": "2026-09-17", "time": null}
Customer Message: "Is 9:00 PM open?"
Updated State: {"intent": "booking", "party_size": 2, "date": "2026-09-17", "time": "21:00"}

Current State: {"intent": "booking", "party_size": 6, "date": "2026-09-20", "time": "12:30", "food_preference": {}}
Customer Message: "Actually, we decided to eat at home instead so I don't want to book anymore. Do you offer takeout catering boxes?"
Updated State: {"intent": "inquiry", "party_size": 6, "date": "2026-09-20", "time": "12:30", "food_preference": {}}

Current State: {"intent": "booking", "party_size": null, "date": null, "time": null, "food_preference": {"vegetarian": 1}}
Customer Message: "Actually, make it vegan."
Updated State: {"intent": "booking", "party_size": null, "date": null, "time": null, "food_preference": {"vegan": 1}}

Current State: {"intent": "booking", "party_size": 4, "date": "2026-09-16", "time": "19:00", "food_preference": {"dairy-free": 2, "non_vegetarian": 2}}
Customer Message: "Actually, scratch that - the dairy-free guests aren't coming anymore, so no dietary requirements for the table."
Updated State: {"intent": "booking", "party_size": 4, "date": "2026-09-16", "time": "19:00", "food_preference": {}}
"""

# ---------------------------------------------------------------------------
# Extraction & Validation Logic
# ---------------------------------------------------------------------------
def extract_booking_info(message: str, base_date: Optional[datetime.date] = None) -> dict:
    # 1. Resolve API Key configuration
    api_key = os.environ.get("GROQ_API_KEY")

    if not api_key:
        return {
            "error": "GROQ_API_KEY is not set. Please set your Groq key before running:\n"
                     "  In PowerShell: $env:GROQ_API_KEY = 'gsk_your_key_here'\n"
                     "  Or create a .env file with: GROQ_API_KEY=gsk_your_key_here"
        }

    base_url = "https://api.groq.com/openai/v1"
    preferred_model = os.environ.get("LLM_MODEL", "openai/gpt-oss-safeguard-20b")
    models_to_try = [
        "openai/gpt-oss-safeguard-20b",
        preferred_model,
        "openai/gpt-oss-20b",
        "groq/compound-mini",
        "openai/gpt-oss-120b",
        "groq/compound",
        "qwen/qwen3.8-27b",
        "allam-2-7b"
    ]

    # Deduplicate while preserving order
    seen = set()
    models_to_try = [m for m in models_to_try if m and not (m in seen or seen.add(m))]

    last_error = None
    raw_content = None

    if base_date is None:
        ref_env = os.environ.get("REFERENCE_DATE")
        if ref_env:
            try:
                base_date = datetime.date.fromisoformat(ref_env)
            except Exception:
                base_date = datetime.date.today()
        else:
            base_date = datetime.date.today()

    today = base_date
    cal_ref = build_reference_calendar(today)

    # 2. Send request to LLM API (with automatic fallback if model not found)
    for model in models_to_try:
        model_succeeded = False
        for attempt in range(4):
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
                        "max_tokens": 1500
                    },
                    timeout=30
                )
            except requests.exceptions.RequestException as err:
                last_error = f"API request failed: Connection error ({err})"
                break

            if response.status_code == 200:
                try:
                    result_data = response.json()
                    raw_content = result_data["choices"][0]["message"]["content"]
                    if raw_content and raw_content.strip():
                        model_succeeded = True
                        break
                except (KeyError, IndexError, json.JSONDecodeError) as err:
                    last_error = f"Invalid response structure from API: {err}"
                    break
            else:
                try:
                    err_json = response.json()
                    err_msg = err_json.get("error", {}).get("message", response.text)
                except Exception:
                    err_msg = response.text
                last_error = f"API error ({response.status_code}): {err_msg}"
                if response.status_code == 429:
                    if "daily" in err_msg.lower() or "limit: 0" in err_msg.lower():
                        break
                    time.sleep(3.0 * (attempt + 1))
                    continue
                elif response.status_code in (400, 404):
                    time.sleep(0.5)
                    break
                else:
                    return {"error": last_error}
        if model_succeeded:
            break

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

    missing_fields = [field for field in ("intent", "party_size", "date", "time") if field not in data]
    if missing_fields:
        return {"error": f"Missing required field(s) in LLM response: {missing_fields}"}

    res = normalize_booking_data(data, base_date=today, message=message)
    if isinstance(res, dict) and "error" not in res:
        # Standard booking schema guarantees the 6 core fields
        output = {
            "intent": res.get("intent", "booking"),
            "party_size": res.get("party_size"),
            "date": res.get("date"),
            "time": res.get("time"),
            "food_preference": res.get("food_preference", {}),
            "summary": res.get("summary")
        }
        # Include auxiliary preferences (e.g. seating_preference, accessibility_requirement) if present
        for k, v in res.items():
            if k not in output and (k.endswith("_preference") or k.endswith("_requirement")):
                output[k] = v
        return output
    return res

def parse_time_expression(time_val: Optional[str]) -> Optional[str]:
    """Normalizes 12-hour/24-hour time expressions to HH:MM format."""
    if not time_val:
        return None
    time_val = str(time_val).strip()
    if re.match(r"^(?:[01]\d|2[0-3]):[0-5]\d$", time_val):
        return time_val
    match_12h = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(?:in the evening|in the afternoon|in the morning)?\s*(am|pm)?", time_val, re.IGNORECASE)
    if match_12h:
        h = int(match_12h.group(1))
        m = int(match_12h.group(2) or 0)
        meridiem = (match_12h.group(3) or "").lower()
        is_evening = "evening" in time_val.lower() or "pm" in time_val.lower()
        if (is_evening or meridiem == "pm") and h < 12:
            h += 12
        elif (not is_evening and meridiem == "am") and h == 12:
            h = 0
        return f"{h:02d}:{m:02d}"
    return None

def generate_extraction_summary(
    intent: str,
    party_size: Optional[int],
    date: Optional[str],
    time: Optional[str],
    food_pref: Optional[dict],
    message: Optional[str] = None
) -> str:
    """
    Deterministic summary generator following the 8 summary rules:
    1. Always returns a string, never null or omitted.
    2. Based only on explicitly provided information.
    3. Never invents or assumes missing information.
    4. Short, clear, and natural.
    5. Includes important extracted parameters.
    6. Reflects latest information.
    7. If only one piece of information, summarizes only that.
    8. Suitable for restaurant booking conversation.
    """
    msg = (message or "").strip()
    msg_lower = msg.lower()

    if intent == "cancellation" or re.search(r"\b(?:cancel|cancellation)\b", msg_lower):
        return "Customer wants to cancel their reservation."

    if intent == "inquiry":
        if "catering" in msg_lower or "takeout" in msg_lower:
            return "Customer is inquiring about takeout catering boxes."
        elif "vegan" in msg_lower or "vegetarian" in msg_lower or "gluten" in msg_lower or "diet" in msg_lower or "menu" in msg_lower:
            return "Customer is inquiring about dietary and menu options."
        elif "hour" in msg_lower or "open" in msg_lower or "close" in msg_lower:
            return "Customer is inquiring about restaurant hours."
        return "Customer is inquiring about restaurant information."

    if intent == "modification":
        return "Customer wants to modify their reservation."

    # Intent is booking:
    # Rule 6 / Example 3: "Make it 6 people instead" -> "Customer wants a table for 6 people."
    if re.search(r"\b(?:make\s+it|make\s+that|just|only|instead)\b", msg_lower) and party_size and not date and not time and not food_pref:
        return f"Customer wants a table for {party_size} people."

    # Rule 5 / Example 4: "I need a vegetarian table for 3" -> "Customer wants to book a table for 3 vegetarian guests."
    if food_pref and isinstance(food_pref, dict) and party_size:
        restrictions = {k: v for k, v in food_pref.items() if k != "non_vegetarian" and isinstance(v, int)}
        if len(restrictions) == 1:
            tag, count = list(restrictions.items())[0]
            if count == party_size:
                return f"Customer wants to book a table for {party_size} {tag} guests."

    # Extract human-readable time expression from message if available (e.g. "8 PM", "7:30 PM")
    time_str = None
    if time:
        if "at " in msg_lower:
            m_at = re.search(r"\bat\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b", msg, re.IGNORECASE)
            time_str = f"at {m_at.group(1)}" if m_at else f"at {time}"
        elif "around " in msg_lower:
            m_ar = re.search(r"\baround\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b", msg, re.IGNORECASE)
            time_str = f"around {m_ar.group(1)}" if m_ar else f"at {time}"
        else:
            time_str = f"at {time}"

    # Extract human-readable date expression from message if available (e.g. "tomorrow", "tonight", "this Friday")
    date_str = None
    if date:
        if "tomorrow" in msg_lower:
            date_str = "tomorrow"
        elif "tonight" in msg_lower:
            date_str = "tonight"
        elif "today" in msg_lower:
            date_str = "today"
        elif "this " in msg_lower:
            m_wd = re.search(r"\bthis\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", msg_lower)
            date_str = m_wd.group(0) if m_wd else f"on {date}"
        elif "on " in msg_lower:
            m_on = re.search(r"\bon\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", msg_lower)
            date_str = m_on.group(0) if m_on else f"on {date}"
        else:
            date_str = f"on {date}"

    # Dietary restriction details
    diet_str = None
    if food_pref and isinstance(food_pref, dict):
        restrictions = {k: v for k, v in food_pref.items() if k != "non_vegetarian" and isinstance(v, int)}
        if restrictions:
            parts = []
            for tag, count in restrictions.items():
                parts.append(f"{count} {tag} guest" if count == 1 else f"{count} {tag} guests")
            diet_str = f"with {', '.join(parts)}"

    # Construct the final natural sentence based only on explicitly provided pieces
    elements = []
    if party_size:
        elements.append(f"for {party_size} people" if party_size != 1 else "for 1 person")
    if date_str:
        elements.append(date_str)
    if time_str:
        elements.append(time_str)
    if diet_str:
        elements.append(diet_str)

    if elements:
        return f"Customer wants to book a table {' '.join(elements)}."
    elif party_size:
        return f"Customer wants to book a table for {party_size} people."
    elif date_str:
        return f"Customer wants to book a table {date_str}."
    elif time_str:
        return f"Customer wants to book a table {time_str}."
    elif diet_str:
        return f"Customer noted dietary requirements: {diet_str}."
    else:
        return "Customer wants to book a table."

def normalize_booking_data(data: dict, base_date: Optional[datetime.date] = None, message: Optional[str] = None) -> dict:
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

    # Handle mid-sentence self-corrections, explicit changes, or weekday mentions if message is provided
    if message:
        m_change = re.search(r"\b(?:change|switch|move|reschedule)(?:\s+the)?\s+(?:date|day)\s+to\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", message, re.IGNORECASE)
        m_corr = re.search(r"\b(?:sorry|wait|actually|make\s+that|meant)\s+(?:i\s+meant\s+)?(?:on\s+|for\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b|\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+instead\b", message, re.IGNORECASE)
        m_this = re.search(r"\bthis\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", message, re.IGNORECASE)
        m_plain = re.search(r"\b(?:on\s+|for\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", message, re.IGNORECASE)
        if m_change:
            date_val = resolve_calendar_date(m_change.group(1), base_date=base_date)
        elif m_corr:
            date_val = resolve_calendar_date(m_corr.group(1) or m_corr.group(2), base_date=base_date)
        elif m_this:
            date_val = resolve_calendar_date(m_this.group(0), base_date=base_date)
        elif m_plain:
            resolved_plain = resolve_calendar_date(m_plain.group(0), base_date=base_date)
            if resolved_plain:
                date_val = resolved_plain

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
                        val = party_size  # clamp impossible counts to party size
                except (ValueError, TypeError):
                    val = None

            # Combine counts if synonym already normalized to the same canonical key (Rule 7)
            if clean_k in normalized:
                if normalized[clean_k] is not None and val is not None:
                    combined_val = normalized[clean_k] + val
                    if party_size is not None and combined_val > party_size:
                        combined_val = party_size
                    normalized[clean_k] = combined_val
                elif val is not None:
                    normalized[clean_k] = val
            else:
                normalized[clean_k] = val
        return normalized

    result = {
        "intent": intent_val,
        "party_size": party_size,
        "date": date_val,
        "time": time_val
    }

    # 6. Normalize food_preference (always present in returned dict)
    raw_food = data.get("food_preference")
    normalized_food = {}
    if isinstance(raw_food, dict):
        normalized_food = normalize_pref_dict(raw_food)
    elif isinstance(raw_food, list):
        # Backward compatibility for list of strings
        for item in raw_food:
            clean_tag = FOOD_SYNONYMS.get(str(item).strip().lower(), str(item).strip().lower())
            if clean_tag:
                if clean_tag in normalized_food and isinstance(normalized_food[clean_tag], int):
                    normalized_food[clean_tag] += 1
                else:
                    normalized_food[clean_tag] = 1

    # Check if message explicitly mentions singular person ("someone", "somebody", "one guest", "one of us")
    # or all guests ("all", "all of us", "everyone", "everybody") with a preference whose count is currently None
    if message and normalized_food:
        for pref_key, count_val in list(normalized_food.items()):
            if count_val is None and pref_key != "non_vegetarian":
                if re.search(r"\b(?:all|everyone|everybody|all\s+of\s+us|entire\s+party|whole\s+party|all\s+meals?)\b", message, re.IGNORECASE) and party_size:
                    normalized_food[pref_key] = party_size
                elif re.search(r"\b(?:someone|somebody|a\s+guest|one\s+guest|one\s+of\s+us|a\s+person|one\s+person)\b", message, re.IGNORECASE):
                    if not re.search(r"\bsome\s+(?:guests|people|of\s+our\s+guests|friends)\b", message, re.IGNORECASE):
                        normalized_food[pref_key] = 1

    # Recalculate/validate food preference consistency with party_size
    if party_size is not None and normalized_food:
        restricted_count = sum(
            v for k, v in normalized_food.items()
            if k != "non_vegetarian" and isinstance(v, int)
        )
        has_explicit_non_veg = (
            "non_vegetarian" in normalized_food
            or (message and re.search(r"\b(?:non-veg|non-vegetarian|non\s+veg|meat\s+eaters?)\b", message, re.IGNORECASE))
        )
        if has_explicit_non_veg:
            if restricted_count >= party_size:
                normalized_food.pop("non_vegetarian", None)
            else:
                curr_non_veg = normalized_food.get("non_vegetarian")
                if curr_non_veg is None or curr_non_veg + restricted_count > party_size:
                    normalized_food["non_vegetarian"] = party_size - restricted_count
        else:
            # Rule 3: Do not invent a preference that the customer did not explicitly state
            normalized_food.pop("non_vegetarian", None)

    result["food_preference"] = normalized_food

    # 7. Normalize other preference categories (seating_preference, accessibility_requirement, etc.)
    for field_name, field_val in data.items():
        if field_name in ("intent", "party_size", "date", "time", "food_preference", "summary"):
            continue
        if field_name.endswith("_preference") or field_name.endswith("_requirement") or "preference" in field_name or "requirement" in field_name:
            if isinstance(field_val, dict):
                result[field_name] = normalize_pref_dict(field_val)
            elif isinstance(field_val, str) and field_val.strip():
                result[field_name] = {field_val.strip().lower(): party_size if party_size else 1}

    # 8. Normalize and attach summary
    summary_val = data.get("summary")
    if not summary_val or not isinstance(summary_val, str) or not summary_val.strip() or summary_val.strip().lower() == "null":
        summary_val = generate_extraction_summary(
            intent=result["intent"],
            party_size=result["party_size"],
            date=result["date"],
            time=result["time"],
            food_pref=result["food_preference"],
            message=message
        )
    result["summary"] = summary_val.strip()

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
    preferred_model = os.environ.get("LLM_MODEL", "openai/gpt-oss-safeguard-20b")
    models_to_try = [
        "openai/gpt-oss-safeguard-20b",
        preferred_model,
        "openai/gpt-oss-20b",
        "groq/compound-mini",
        "openai/gpt-oss-120b",
        "groq/compound",
        "qwen/qwen3.8-27b",
        "allam-2-7b"
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
        model_succeeded = False
        for attempt in range(4):
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
                        "max_tokens": 1500
                    },
                    timeout=30
                )
            except requests.exceptions.RequestException as err:
                last_error = f"API request failed: Connection error ({err})"
                break

            if response.status_code == 200:
                try:
                    result_data = response.json()
                    raw_content = result_data["choices"][0]["message"]["content"]
                    if raw_content and raw_content.strip():
                        model_succeeded = True
                        break
                except (KeyError, IndexError, json.JSONDecodeError) as err:
                    last_error = f"Invalid response structure from API: {err}"
                    break
            else:
                try:
                    err_json = response.json()
                    err_msg = err_json.get("error", {}).get("message", response.text)
                except Exception:
                    err_msg = response.text
                last_error = f"API error ({response.status_code}): {err_msg}"
                if response.status_code == 429:
                    if "daily" in err_msg.lower() or "limit: 0" in err_msg.lower():
                        break
                    time.sleep(3.0 * (attempt + 1))
                    continue
                elif response.status_code in (400, 404):
                    time.sleep(0.5)
                    break
                else:
                    return {"error": last_error}
        if model_succeeded:
            break

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

    normalized = normalize_booking_data(data, base_date=today, message=message)

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
            normalized = normalize_booking_data(normalized, base_date=today, message=message)

    msg_lower = message.lower()

    # Slot retention: Preserve parameters from base_state unless explicitly removed
    if base_state.get("party_size") is not None and normalized.get("party_size") is None:
        if not re.search(r"\b(?:cancel|remove|clear)\s+(?:the\s+)?party\s*size\b", msg_lower):
            normalized["party_size"] = base_state["party_size"]

    # Date preservation: Only change date when customer explicitly provides or changes a date
    DATE_MENTION_PATTERN = r"\b(?:today|tonight|tomorrow|day\s+after\s+tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday|january|february|march|april|may|june|july|august|september|october|november|december|date|day)\b|\b\d{4}-\d{2}-\d{2}\b"
    if base_state.get("date") is not None:
        if not re.search(DATE_MENTION_PATTERN, msg_lower):
            normalized["date"] = base_state["date"]
    elif normalized.get("date") is None and base_state.get("date") is not None:
        if not re.search(r"\b(?:cancel|remove|clear|never\s*mind)\s+(?:the\s+)?date\b|\b(?:any\s+day|any\s+date)\s+is\s+(?:fine|good|okay)\b", msg_lower):
            normalized["date"] = base_state["date"]

    # Time preservation: Only change time when customer explicitly provides or adjusts a time
    TIME_MENTION_PATTERN = r"\b(?:am|pm|o'clock|noon|midnight|morning|afternoon|evening|night|hour\s+earlier|hour\s+later|earlier|later|time|\d{1,2}:\d{2}|\d{1,2}\s*(?:am|pm))\b"
    if base_state.get("time") is not None:
        if not re.search(TIME_MENTION_PATTERN, msg_lower):
            normalized["time"] = base_state["time"]
    elif normalized.get("time") is None and base_state.get("time") is not None:
        if not re.search(r"\b(?:cancel|remove|clear|never\s*mind)\s+(?:the\s+)?time\b|\b(?:any\s+time|anytime)\s+is\s+(?:fine|good|okay)\b", msg_lower):
            normalized["time"] = base_state["time"]

    # Inquiries about time availability during booking flow (e.g. "Is 9:00 PM open?")
    time_q_match = re.search(r"\b(?:is|can we do|how about|table at)\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s*(?:open|available|work)?\b", msg_lower)
    if time_q_match:
        from intent_classifier import parse_time_expression
        parsed_t = parse_time_expression(time_q_match.group(1))
        if parsed_t:
            normalized["time"] = parsed_t
            if normalized.get("intent") in ("inquiry", "booking") and (base_state.get("party_size") or base_state.get("date")):
                normalized["intent"] = "booking"

    # Colloquial relative time shifts ("make it an hour earlier / later")
    if re.search(r"\b(?:an\s+hour|1\s+hour)\s+earlier\b", msg_lower):
        if normalized.get("time") == base_state.get("time"):
            curr_time = base_state.get("time")
            if curr_time and ":" in str(curr_time):
                h, m = map(int, curr_time.split(":")[:2])
                normalized["time"] = f"{(h - 1) % 24:02d}:{m:02d}"
    elif re.search(r"\b(?:an\s+hour|1\s+hour)\s+later\b", msg_lower):
        if normalized.get("time") == base_state.get("time"):
            curr_time = base_state.get("time")
            if curr_time and ":" in str(curr_time):
                h, m = map(int, curr_time.split(":")[:2])
                normalized["time"] = f"{(h + 1) % 24:02d}:{m:02d}"

    # Incremental dietary accumulation: preserve confirmed restrictions when another is added
    if isinstance(base_state.get("food_preference"), dict) and base_state.get("food_preference"):
        from state_manager import FOOD_REMOVAL_PATTERNS
        is_removal = any(re.search(p, msg_lower, re.IGNORECASE) for p in FOOD_REMOVAL_PATTERNS)
        is_substitution = bool(re.search(r"\b(?:actually|instead|rather than|switch to|change to)\b.*\b(?:vegan|vegetarian|gluten|dairy|nut|halal|kosher)\b", msg_lower)) and not re.search(r"\b(?:and|also|both|in addition)\b", msg_lower)
        if not is_removal and not is_substitution:
            if not isinstance(normalized.get("food_preference"), dict):
                normalized["food_preference"] = dict(base_state["food_preference"])
            else:
                for k, v in base_state["food_preference"].items():
                    if k != "non_vegetarian" and k not in normalized["food_preference"]:
                        normalized["food_preference"][k] = v

    # Conversational food removals
    from state_manager import FOOD_REMOVAL_PATTERNS
    for pattern in FOOD_REMOVAL_PATTERNS:
        if re.search(pattern, msg_lower, re.IGNORECASE):
            normalized["food_preference"] = {}
            break

    # Dietary requirement substitution: "make it vegan instead of vegetarian" / "make it vegan"
    if re.search(r"\b(?:actually|instead|rather than|switch to|change to)\b.*\bvegan\b", msg_lower) and not re.search(r"\b(?:and|also|both|in addition)\b", msg_lower):
        if isinstance(normalized.get("food_preference"), dict):
            normalized["food_preference"].pop("vegetarian", None)
            if "vegan" not in normalized["food_preference"]:
                normalized["food_preference"]["vegan"] = 1

    # Re-normalize to guarantee consistency
    normalized = normalize_booking_data(normalized, base_date=today, message=message)

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

