"""
Conversation State Management System for Restaurant Booking.

This module provides lightweight in-memory state tracking across multi-turn
customer conversations. It maintains booking parameters, handles incremental
slot additions, updates/corrections, removals, and intent transitions while
keeping previously provided information intact.
"""

import re
from typing import Dict, List, Optional, Any

# Canonical default state schema
DEFAULT_STATE = {
    "intent": "booking",
    "party_size": None,
    "date": None,
    "time": None,
    "food_preference": []
}

# Regex patterns to identify removal/clearing intent for specific fields
FOOD_REMOVAL_PATTERNS = [
    r"\b(?:no|none|zero|without\s+any)\s+(?:allergies|allergy|dietary|restrictions?|food\s+preferences?)\b",
    r"\b(?:remove|clear|cancel)\s+(?:all\s+)?(?:allergies|dietary(?:\s+requirements?|\s+restrictions?)?)\b",
    r"\bno\s+special\s+diet(?:ary)?\b",
    r"\bno\s+longer\s+(?:have|need)\s+(?:dietary|allergies)\b",
    r"\bnever\s*mind\s+(?:the\s+)?(?:allergies|dietary)\b",
    r"\beveryone\s+eats\s+everything\b",
    r"\bno\s+food\s+restrictions?\b"
]

SEATING_REMOVAL_PATTERNS = [
    r"\b(?:no|cancel|remove|clear|never\s*mind)\s+(?:the\s+)?(?:seating|seat|seats|table|window|booth)\b",
    r"\bany\s+(?:table|seat|seating)\s+is\s+(?:fine|good|okay)\b",
    r"\bdon't\s+care\s+(?:about\s+)?(?:where\s+we\s+sit|seating)\b"
]

ACCESSIBILITY_REMOVAL_PATTERNS = [
    r"\b(?:no|cancel|remove|clear|never\s*mind|don't\s+need|do\s+not\s+need)\s+(?:the\s+)?(?:accessibility|wheelchair|wheelchair\s+access|high\s*chair|stroller)\b",
    r"\bno\s+accessibility\s+needs?\b"
]

CELEBRATION_REMOVAL_PATTERNS = [
    r"\b(?:no|cancel|remove|clear|never\s*mind)\s+(?:the\s+)?(?:birthday|anniversary|celebration)\b",
    r"\bnot\s+a\s+special\s+occasion\b"
]

DATE_REMOVAL_PATTERNS = [
    r"\b(?:cancel|remove|clear)\s+(?:the\s+)?date\b",
    r"\bnever\s*mind\s+(?:the\s+)?date\b",
    r"\b(?:any\s+day|any\s+date)\s+is\s+(?:fine|good|okay)\b"
]

TIME_REMOVAL_PATTERNS = [
    r"\b(?:cancel|remove|clear)\s+(?:the\s+)?time\b",
    r"\bnever\s*mind\s+(?:the\s+)?time\b",
    r"\b(?:any\s+time|anytime)\s+is\s+(?:fine|good|okay)\b"
]

PARTY_SIZE_REMOVAL_PATTERNS = [
    r"\b(?:cancel|remove|clear)\s+(?:the\s+)?party\s*size\b",
    r"\bnot\s+sure\s+about\s+(?:the\s+)?(?:number\s+of\s+people|guest\s+count|party\s*size)\b"
]

# Regex patterns to identify explicit customer correction / slot replacement
CORRECTION_PATTERNS = [
    r"\b(?:actually|sorry|instead|rather\s+than|rather|scratch\s+that)\b",
    r"\b(?:change(?:\s+it|\s+that)?(?:\s+to)?|switch(?:\s+to)?|update(?:\s+to)?|make\s+it|make\s+that)\b",
    r"\b(?:no\s*,\s*|no\s+)(?:i\s+want|we\s+want|make\s+it|let's\s+do|i\s+meant|we\s+meant)\b",
    r"\bi\s+changed\s+my\s+mind\b",
    r"\b(?:i\s+meant|meant\s+to\s+say|correction)\b",
    r"\b(?:wait\s*,\s*no|wait\s+no)\b",
]

def is_explicit_correction(message: str) -> bool:
    """Checks whether the customer message contains explicit correction / replacement signals."""
    if not message:
        return False
    msg_lower = message.lower()
    return any(re.search(p, msg_lower) for p in CORRECTION_PATTERNS)

def is_additive_signal(message: str) -> bool:
    """Checks whether the customer message indicates adding to existing requirements rather than replacing."""
    if not message:
        return False
    msg_lower = message.lower()
    return bool(re.search(r"\b(?:also|and\s+another|and\s+also|in\s+addition|another|as\s+well|plus)\b", msg_lower))

def has_all_semantics(message: str) -> bool:
    """Checks whether the message specifies a preference for the entire party/all guests."""
    if not message:
        return False
    msg_lower = message.lower()
    return bool(re.search(r"\b(?:all|everyone|everybody|all\s+of\s+us|entire\s+party|whole\s+party|all\s+meals?|all\s+guests?)\b", msg_lower))


class BookingState:
    """
    Maintains the state of a restaurant booking conversation across turns.
    """

    def __init__(self, initial_state: Optional[Dict[str, Any]] = None):
        """Initialize booking state with default or provided values."""
        self.intent: str = "booking"
        self.party_size: Optional[int] = None
        self.date: Optional[str] = None
        self.time: Optional[str] = None
        self.food_preference: Any = []
        self.seating_preference: Dict[str, Any] = {}
        self.accessibility_requirement: Dict[str, Any] = {}
        self.celebration_requirement: Dict[str, Any] = {}
        self.other_preferences: Dict[str, Any] = {}
        self.customer_name: Optional[str] = None
        self.booking_id: Optional[str] = None
        self.all_food_preference: Optional[str] = None
        self.history: List[Dict[str, Any]] = []
        self.conversation_messages: List[Dict[str, str]] = []

        if initial_state:
            self.load_from_dict(initial_state)

    def to_dict(self, include_metadata: bool = False) -> Dict[str, Any]:
        """Returns the canonical state dictionary (or with metadata if requested)."""
        d = {
            "intent": self.intent,
            "party_size": self.party_size,
            "date": self.date,
            "time": self.time,
            "food_preference": dict(self.food_preference) if isinstance(self.food_preference, dict) else list(self.food_preference)
        }
        if self.seating_preference:
            d["seating_preference"] = dict(self.seating_preference)
        if self.accessibility_requirement:
            d["accessibility_requirement"] = dict(self.accessibility_requirement)
        if self.celebration_requirement:
            d["celebration_requirement"] = dict(self.celebration_requirement)
        for k, v in getattr(self, "other_preferences", {}).items():
            if v:
                d[k] = dict(v) if isinstance(v, dict) else v
        if include_metadata:
            if getattr(self, "customer_name", None):
                d["customer_name"] = self.customer_name
            if getattr(self, "booking_id", None):
                d["booking_id"] = self.booking_id
        return d

    def reset(self) -> Dict[str, Any]:
        """Resets all fields to their initial defaults and clears history."""
        self.intent = "booking"
        self.party_size = None
        self.date = None
        self.time = None
        self.food_preference = []
        self.seating_preference = {}
        self.accessibility_requirement = {}
        self.celebration_requirement = {}
        self.other_preferences = {}
        self.customer_name = None
        self.booking_id = None
        self.all_food_preference = None
        self.history = []
        self.conversation_messages = []
        return self.to_dict()

    def set_field(self, field: str, value: Any) -> None:
        """
        Manually sets or updates a specific state field.
        """
        if field == "intent":
            self.intent = str(value).strip().lower() if value else "booking"
        elif field == "party_size":
            if value is None:
                self.party_size = None
            else:
                try:
                    val = int(value)
                    self.party_size = val if val > 0 else None
                except (ValueError, TypeError):
                    self.party_size = None
        elif field == "date":
            self.date = str(value).strip() if value else None
        elif field == "time":
            self.time = str(value).strip() if value else None
        elif field == "customer_name":
            self.customer_name = str(value).strip() if value else None
        elif field == "booking_id":
            self.booking_id = str(value).strip() if value else None
        elif field == "food_preference":
            if isinstance(value, dict):
                self.food_preference = dict(value)
            elif isinstance(value, list):
                self.food_preference = [str(x).strip().lower() for x in value if x]
            elif isinstance(value, str):
                self.food_preference = [value.strip().lower()] if value.strip() else []
            else:
                self.food_preference = {}
        elif field == "seating_preference":
            self.seating_preference = dict(value) if isinstance(value, dict) else {}
        elif field == "accessibility_requirement":
            self.accessibility_requirement = dict(value) if isinstance(value, dict) else {}
        elif field == "celebration_requirement":
            self.celebration_requirement = dict(value) if isinstance(value, dict) else {}
        elif field.endswith("_preference") or field.endswith("_requirement"):
            if not hasattr(self, "other_preferences"):
                self.other_preferences = {}
            self.other_preferences[field] = dict(value) if isinstance(value, dict) else value
        else:
            raise KeyError(f"Unknown state field: '{field}'")

    def remove_field(self, field: str) -> None:
        """
        Removes / clears a specific field from the state.
        """
        if field == "food_preference":
            self.food_preference = {} if isinstance(self.food_preference, dict) else []
            self.all_food_preference = None
        elif field == "seating_preference":
            self.seating_preference = {}
        elif field == "accessibility_requirement":
            self.accessibility_requirement = {}
        elif field == "celebration_requirement":
            self.celebration_requirement = {}
        elif hasattr(self, "other_preferences") and field in self.other_preferences:
            del self.other_preferences[field]
        elif field in ("party_size", "date", "time", "customer_name", "booking_id"):
            setattr(self, field, None)
        elif field == "intent":
            self.intent = "booking"
        else:
            raise KeyError(f"Unknown state field: '{field}'")

    def remove_dietary_preference(self, item: str) -> bool:
        """
        Removes a specific dietary requirement tag if present.
        Returns True if removed, False otherwise.
        """
        normalized = item.strip().lower()
        if isinstance(self.food_preference, dict):
            if normalized in self.food_preference:
                del self.food_preference[normalized]
                self.all_food_preference = None
                return True
        elif isinstance(self.food_preference, list):
            if normalized in self.food_preference:
                self.food_preference.remove(normalized)
                self.all_food_preference = None
                return True
        return False

    def load_from_dict(self, data: Dict[str, Any]) -> None:
        """Loads state from an existing dictionary."""
        for field in ("intent", "party_size", "date", "time", "customer_name", "booking_id",
                      "food_preference", "seating_preference", "accessibility_requirement",
                      "celebration_requirement"):
            if field in data:
                self.set_field(field, data[field])
        for k, v in data.items():
            if (k.endswith("_preference") or k.endswith("_requirement")) and k not in (
                "food_preference", "seating_preference", "accessibility_requirement", "celebration_requirement"
            ):
                self.set_field(k, v)

    def _check_negation_removals(self, message: str) -> None:
        """Inspects customer message for conversational removal signals."""
        msg_lower = message.lower()

        # Food preference removal check
        for pattern in FOOD_REMOVAL_PATTERNS:
            if re.search(pattern, msg_lower, re.IGNORECASE):
                self.food_preference = {} if isinstance(self.food_preference, dict) else []
                self.all_food_preference = None
                break

        # Seating preference removal check
        for pattern in SEATING_REMOVAL_PATTERNS:
            if re.search(pattern, msg_lower, re.IGNORECASE):
                self.seating_preference = {}
                break

        # Accessibility requirement removal check
        for pattern in ACCESSIBILITY_REMOVAL_PATTERNS:
            if re.search(pattern, msg_lower, re.IGNORECASE):
                self.accessibility_requirement = {}
                break

        # Celebration requirement removal check
        for pattern in CELEBRATION_REMOVAL_PATTERNS:
            if re.search(pattern, msg_lower, re.IGNORECASE):
                self.celebration_requirement = {}
                break

        # Date removal check
        for pattern in DATE_REMOVAL_PATTERNS:
            if re.search(pattern, msg_lower, re.IGNORECASE):
                self.date = None
                break

        # Time removal check
        for pattern in TIME_REMOVAL_PATTERNS:
            if re.search(pattern, msg_lower, re.IGNORECASE):
                self.time = None
                break

        # Party size removal check
        for pattern in PARTY_SIZE_REMOVAL_PATTERNS:
            if re.search(pattern, msg_lower, re.IGNORECASE):
                self.party_size = None
                break

    def apply_extraction(self, extracted: Dict[str, Any], message: str = "") -> Dict[str, Any]:
        """
        Merges newly extracted parameters into the current conversation state.

        Rules applied:
        1. Intent: Updates to the latest identified intent.
        2. Party size: Overwrites if newly provided (non-null), otherwise keeps existing.
        3. Date: Overwrites if newly provided (non-null), otherwise keeps existing.
        4. Time: Overwrites if newly provided (non-null), otherwise keeps existing.
        5. Food preference: Updates preference dictionary with exact person counts.
        6. Removals: If the message requests removing/clearing fields, resets them.
        7. Recalculates/validates preference counts against latest party_size.
        """
        if not isinstance(extracted, dict):
            return self.to_dict()

        # Check for error in extraction
        if "error" in extracted:
            return self.to_dict()

        # 1. Update intent
        new_intent = extracted.get("intent")
        if new_intent and str(new_intent).strip():
            cleaned_intent = str(new_intent).strip().lower()
            msg_lower = message.lower() if message else ""
            stopped_booking = bool(re.search(r"\b(?:don't|do not|stop|cancel|no longer)\s+(?:want\s+to\s+)?(?:book|reserve)\b", msg_lower))
            has_question = bool("?" in msg_lower or re.search(r"\b(?:can you|could you|what|when|where|how|hours|time|menu|offer|catering|takeout|do you)\b", msg_lower))

            if stopped_booking:
                if has_question or cleaned_intent == "inquiry":
                    self.intent = "inquiry"
                else:
                    self.intent = "cancellation"
            else:
                has_booking_updates = any(extracted.get(k) is not None for k in ("party_size", "date", "time")) or bool(extracted.get("food_preference"))
                if self.intent == "booking" and cleaned_intent in ("modification", "booking"):
                    self.intent = "booking"
                elif self.intent == "booking" and cleaned_intent == "inquiry" and has_booking_updates:
                    self.intent = "booking"
                else:
                    self.intent = cleaned_intent

        # 2. Check for explicit conversational removals first
        if message:
            self._check_negation_removals(message)

        # 3. Update party size (add / overwrite / keep)
        new_party_size = extracted.get("party_size")
        party_size_changed = False
        if new_party_size is not None:
            if self.party_size is not None and new_party_size != self.party_size and message:
                msg_lower = message.lower()
                explicit_party_patterns = [
                    r"\b(?:make\s+it|make\s+that)\s+(?:\w+\s+)*(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\b",
                    r"\b(?:change|switch|update)(?:\s+\w+)*\s+to\s+(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\b",
                    r"\b(?:table|booth|party|reservation|seats?)\s+for\s+(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\b",
                    r"\b(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+(?:people|guests|persons|diners|seats|of\s+us)\b",
                    r"\b(?:add|plus)\s+(?:\d+|one|two|three|four|five|six)\s+(?:more\s+)?(?:people|guests|persons|diners|seats)?\b",
                    r"\b(?:just|only)\s+(?:\d+|one|two|three|four|five|six)\s*(?:people|guests|of\s+us)?\b",
                    r"\b(?:actually|sorry|no,?\s*(?:i\s+want)?|scratch\s+that|meant)\s+(?:\w+\s+)*(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\b",
                    r"\b(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+(?:instead)\b",
                    r"\b(?:there\s+will\s+be|we\s+have|we\s+are)\s+(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s*(?:people|guests|of\s+us)?\b",
                ]
                has_explicit_party_change = any(re.search(p, msg_lower) for p in explicit_party_patterns)
                is_preference_mention = bool(re.search(r"\b(?:colleague|friend|partner|spouse|guest|someone|person|one|two|three|four|five|six)\b.*\b(?:vegetarian|vegan|allergy|allergic|gluten|celiac|nut|peanut|dairy|lactose|halal|kosher|pescatarian|diet|wheelchair|window|booth|seating|access|high\s*chair)\b", msg_lower))

                if has_explicit_party_change and not (is_preference_mention and not re.search(r"\b(?:make\s+it|change\s+to|switch\s+to|actually|sorry)\s+\d+\b", msg_lower)):
                    self.party_size = new_party_size
                    party_size_changed = True
                # otherwise preserve current party_size
            else:
                if self.party_size != new_party_size:
                    party_size_changed = True
                self.party_size = new_party_size
        elif self.party_size is None:
            from intent_classifier import extract_explicit_party_size
            explicit_ps = extract_explicit_party_size(message) if message else None
            if explicit_ps is not None and explicit_ps > 0:
                self.party_size = explicit_ps
                party_size_changed = True
            else:
                food_dict = extracted.get("food_preference")
                if isinstance(food_dict, dict) and food_dict:
                    is_partial_mention = bool(message and re.search(
                        r"\b(?:one|some)\s+of\s+(?:our|the|my)\s+(?:guests|friends|colleagues|group|party)\b|\b(?:a|my|another)\s+(?:colleague|friend|partner|spouse)\b|\bone\s+person\s+in\s+the\s+(?:group|party)\b",
                        message,
                        re.IGNORECASE
                    ))
                    if not is_partial_mention:
                        food_counts = [v for v in food_dict.values() if isinstance(v, int) and v > 0]
                        if food_counts:
                            self.party_size = sum(food_counts)
                            party_size_changed = True

        # Rule 5: If party size changed, update dependent preferences
        if party_size_changed and self.party_size is not None:
            if self.all_food_preference and isinstance(self.food_preference, dict):
                self.food_preference = {self.all_food_preference: self.party_size}
            elif isinstance(self.food_preference, dict) and self.food_preference:
                for k, v in list(self.food_preference.items()):
                    if isinstance(v, int) and v > self.party_size:
                        self.food_preference[k] = self.party_size
                total_counts = sum(v for v in self.food_preference.values() if isinstance(v, int))
                if total_counts > self.party_size and "non_vegetarian" in self.food_preference:
                    restricted = sum(v for k, v in self.food_preference.items() if k != "non_vegetarian" and isinstance(v, int))
                    if restricted >= self.party_size:
                        self.food_preference.pop("non_vegetarian", None)
                    else:
                        self.food_preference["non_vegetarian"] = self.party_size - restricted

        # 4. Update date (add / overwrite / keep)
        new_date = extracted.get("date")
        if new_date is not None:
            self.date = new_date

        # 5. Update time (add / overwrite / keep)
        new_time = extracted.get("time")
        if new_time is not None:
            self.time = new_time

        if message:
            msg_lower = message.lower()
            if re.search(r"\b(?:an\s+hour|1\s+hour)\s+earlier\b", msg_lower) and self.time and ":" in str(self.time):
                h, m = map(int, self.time.split(":")[:2])
                self.time = f"{(h - 1) % 24:02d}:{m:02d}"
            elif re.search(r"\b(?:an\s+hour|1\s+hour)\s+later\b", msg_lower) and self.time and ":" in str(self.time):
                h, m = map(int, self.time.split(":")[:2])
                self.time = f"{(h + 1) % 24:02d}:{m:02d}"

            time_q_match = re.search(r"\b(?:is|can we do|how about|table at)\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s*(?:open|available|work)?\b", msg_lower)
            if time_q_match:
                from intent_classifier import parse_time_expression
                parsed_t = parse_time_expression(time_q_match.group(1))
                if parsed_t:
                    self.time = parsed_t
                    if self.intent in ("inquiry", "booking") and (self.party_size or self.date):
                        self.intent = "booking"

        # 6. Update food preference (handle dict with counts or list)
        new_food = extracted.get("food_preference")
        msg_lower = message.lower() if message else ""
        is_correction = is_explicit_correction(msg_lower)
        is_all = has_all_semantics(msg_lower)
        is_additive = is_additive_signal(msg_lower)

        if isinstance(new_food, dict):
            # Check for contradictory dietary requirements
            new_has_non_veg = "non_vegetarian" in new_food
            old_has_veg = isinstance(self.food_preference, dict) and any(k in self.food_preference for k in ("vegetarian", "vegan", "pescatarian"))
            new_has_veg = any(k in new_food for k in ("vegetarian", "vegan", "pescatarian"))
            old_has_non_veg = isinstance(self.food_preference, dict) and "non_vegetarian" in self.food_preference
            has_contradiction = (new_has_non_veg and old_has_veg) or (new_has_veg and old_has_non_veg)

            # Check if new preference covers full table
            is_full_table = False
            if self.party_size and new_food:
                is_full_table = any(v == self.party_size for v in new_food.values() if isinstance(v, int)) or (
                    sum(v for v in new_food.values() if isinstance(v, int)) == self.party_size
                )

            if new_food:
                if (is_correction or is_all or is_full_table or has_contradiction) and not is_additive:
                    # Complete replacement of previous food preferences
                    self.food_preference = dict(new_food)
                    if is_all and len(new_food) == 1:
                        self.all_food_preference = next(iter(new_food.keys()))
                    else:
                        self.all_food_preference = None
                elif is_additive and isinstance(self.food_preference, dict):
                    merged = dict(self.food_preference)
                    merged.update(new_food)
                    self.food_preference = merged
                    self.all_food_preference = None
                elif isinstance(self.food_preference, dict):
                    # Merge preferences, removing any contradictory items
                    merged = dict(self.food_preference)
                    merged.update(new_food)
                    if new_has_non_veg:
                        for k in ("vegetarian", "vegan", "pescatarian"):
                            merged.pop(k, None)
                    elif new_has_veg:
                        merged.pop("non_vegetarian", None)
                    self.food_preference = merged
                    if is_all and len(new_food) == 1:
                        self.all_food_preference = next(iter(new_food.keys()))
                    else:
                        self.all_food_preference = None
                else:
                    self.food_preference = dict(new_food)
                    if is_all and len(new_food) == 1:
                        self.all_food_preference = next(iter(new_food.keys()))
                    else:
                        self.all_food_preference = None
        elif isinstance(new_food, list):
            cleaned_new = [str(x).strip().lower() for x in new_food if x and str(x).strip()]
            if (is_correction or is_all) and not is_additive and cleaned_new:
                self.food_preference = cleaned_new
            elif cleaned_new:
                if isinstance(self.food_preference, list):
                    for item in cleaned_new:
                        if item not in self.food_preference:
                            self.food_preference.append(item)
                else:
                    self.food_preference = cleaned_new

        # Check if party_size can be inferred from food_preference if still None
        if self.party_size is None and isinstance(self.food_preference, dict) and self.food_preference:
            is_partial_mention = bool(message and re.search(
                r"\b(?:one|some)\s+of\s+(?:our|the|my)\s+(?:guests|friends|colleagues|group|party)\b|\b(?:a|my|another)\s+(?:colleague|friend|partner|spouse)\b|\bone\s+person\s+in\s+the\s+(?:group|party)\b",
                message,
                re.IGNORECASE
            ))
            if not is_partial_mention:
                food_counts = [v for v in self.food_preference.values() if isinstance(v, int) and v > 0]
                if food_counts:
                    self.party_size = sum(food_counts)

        # 7. Update other preference fields
        if "seating_preference" in extracted and isinstance(extracted["seating_preference"], dict):
            self.seating_preference = dict(extracted["seating_preference"])
        if "accessibility_requirement" in extracted and isinstance(extracted["accessibility_requirement"], dict):
            self.accessibility_requirement = dict(extracted["accessibility_requirement"])
        if "celebration_requirement" in extracted and isinstance(extracted["celebration_requirement"], dict):
            self.celebration_requirement = dict(extracted["celebration_requirement"])
        for k, v in extracted.items():
            if (k.endswith("_preference") or k.endswith("_requirement")) and k not in (
                "food_preference", "seating_preference", "accessibility_requirement", "celebration_requirement"
            ):
                if not hasattr(self, "other_preferences"):
                    self.other_preferences = {}
                self.other_preferences[k] = dict(v) if isinstance(v, dict) else v

        # 8. Re-validate preference counts against party size (Rule 10)
        if self.party_size is not None:
            if isinstance(self.food_preference, dict) and self.food_preference:
                for k, v in list(self.food_preference.items()):
                    if isinstance(v, int) and v > self.party_size:
                        self.food_preference[k] = self.party_size
                restricted_count = sum(
                    v for k, v in self.food_preference.items()
                    if k != "non_vegetarian" and isinstance(v, int)
                )
                if restricted_count > 0:
                    if restricted_count >= self.party_size:
                        self.food_preference.pop("non_vegetarian", None)
                    elif "non_vegetarian" in self.food_preference and (restricted_count + self.food_preference["non_vegetarian"] > self.party_size):
                        self.food_preference["non_vegetarian"] = self.party_size - restricted_count
            for pref_dict in (self.seating_preference, self.accessibility_requirement, self.celebration_requirement):
                if isinstance(pref_dict, dict):
                    for k, v in list(pref_dict.items()):
                        if isinstance(v, int) and v > self.party_size:
                            pref_dict[k] = self.party_size

        # Record this turn into history
        if message:
            self.history.append({
                "message": message,
                "extracted": extracted,
                "resulting_state": self.to_dict()
            })

        return self.to_dict()

    def process_message(self, message: str) -> Dict[str, Any]:
        """
        Processes an incoming customer message end-to-end using the LLM:
        1. Sends the current conversation state and message to update_booking_state_with_llm.
        2. The LLM determines additions, updates, removals, or intent transitions in context.
        3. Updates internal state and returns the updated state dictionary.
        """
        from intent_classifier import update_booking_state_with_llm
        updated = update_booking_state_with_llm(self.to_dict(), message)

        if isinstance(updated, dict) and "error" not in updated:
            self.load_from_dict(updated)
            self.history.append({
                "message": message,
                "resulting_state": self.to_dict()
            })
            return self.to_dict()
        else:
            # Fallback to rule-based apply_extraction if LLM state update returned an error
            from intent_classifier import extract_booking_info
            extracted = extract_booking_info(message)
            return self.apply_extraction(extracted, message=message)

    def process_turn(self, message: str, preferred_model: Optional[str] = None) -> Dict[str, Any]:
        """
        Integrates multi-turn conversation context/state management with LLM Function Calling:
        1. Updates internal booking state using process_message(message).
        2. Detects explicit customer name mentions if provided.
        3. Invokes the Function Calling engine with conversation messages and accumulated state.
        4. Synchronizes state with any function execution outcomes (e.g. booking ID on creation).
        5. Saves dialogue turns into conversation history.
        6. Returns structured turn summary including state, function called, arguments, and final response.
        """
        # 1. Update accumulated state
        self.process_message(message)

        # Detect customer name if stated (e.g. "My name is Jannatul", "under Jannatul")
        if not getattr(self, "customer_name", None):
            name_match = re.search(r"\b(?:my name is|name is|i am|i'm|under(?:\s+the\s+name)?)\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)\b", message, re.IGNORECASE)
            if name_match:
                self.set_field("customer_name", name_match.group(1).strip())

        # Detect booking ID if stated (e.g. "booking ABC123", "reservation BK-2041", "ID ABC789")
        if not getattr(self, "booking_id", None):
            id_match = re.search(r"\b(?:booking|reservation|id)\s*[:#]?\s*([A-Za-z0-9\-_]{5,10})\b", message, re.IGNORECASE)
            if id_match:
                self.set_field("booking_id", id_match.group(1).strip())

        # 2. Invoke function calling engine with context and current state
        from function_caller import process_customer_request
        history = list(self.conversation_messages) if hasattr(self, "conversation_messages") else []

        turn_result = process_customer_request(
            customer_message=message,
            conversation_history=history,
            current_state=self.to_dict(include_metadata=True),
            state_history=self.history,
            preferred_model=preferred_model
        )

        fn_called = turn_result.get("function_called")
        fn_res = turn_result.get("function_result") or {}
        fn_args = turn_result.get("arguments", {})

        # 3. Synchronize state with function execution results
        if fn_called == "create_booking" and fn_res.get("success"):
            if "booking_id" in fn_res:
                self.set_field("booking_id", fn_res["booking_id"])
            if fn_args.get("customer_name"):
                self.set_field("customer_name", fn_args["customer_name"])
            self.set_field("intent", "booking")
        elif fn_called == "modify_booking" and fn_res.get("success"):
            if fn_args.get("booking_id"):
                self.set_field("booking_id", fn_args["booking_id"])
            if fn_args.get("new_party_size"):
                self.set_field("party_size", fn_args["new_party_size"])
            if fn_args.get("new_date"):
                self.set_field("date", fn_args["new_date"])
            if fn_args.get("new_time"):
                self.set_field("time", fn_args["new_time"])
            self.set_field("intent", "modification")
        elif fn_called == "cancel_booking" and fn_res.get("success"):
            self.set_field("intent", "cancellation")

        # 4. Save to conversational history
        if not hasattr(self, "conversation_messages"):
            self.conversation_messages = []
        self.conversation_messages.append({"role": "user", "content": message})
        final_resp = turn_result.get("final_response", "")
        self.conversation_messages.append({"role": "assistant", "content": final_resp})

        return {
            "customer_message": message,
            "state": self.to_dict(include_metadata=True),
            "function": fn_called,
            "function_called": fn_called,
            "arguments": fn_args,
            "summary": turn_result.get("summary", ""),
            "function_result": fn_res,
            "final_response": final_resp,
            "status": turn_result.get("status")
        }

    def __repr__(self) -> str:
        return f"<BookingState {self.to_dict()}>"
