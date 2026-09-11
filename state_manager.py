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
        self.food_preference: List[str] = []
        self.customer_name: Optional[str] = None
        self.booking_id: Optional[str] = None
        self.history: List[Dict[str, Any]] = []
        self.conversation_messages: List[Dict[str, str]] = []

        if initial_state:
            self.load_from_dict(initial_state)

    def to_dict(self, include_metadata: bool = False) -> Dict[str, Any]:
        """Returns the canonical 5-field state dictionary (or with metadata if requested)."""
        d = {
            "intent": self.intent,
            "party_size": self.party_size,
            "date": self.date,
            "time": self.time,
            "food_preference": list(self.food_preference)
        }
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
        self.customer_name = None
        self.booking_id = None
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
            if isinstance(value, list):
                self.food_preference = [str(x).strip().lower() for x in value if x]
            elif isinstance(value, str):
                self.food_preference = [value.strip().lower()] if value.strip() else []
            else:
                self.food_preference = []
        else:
            raise KeyError(f"Unknown state field: '{field}'")

    def remove_field(self, field: str) -> None:
        """
        Removes / clears a specific field from the state.
        """
        if field == "food_preference":
            self.food_preference = []
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
        if normalized in self.food_preference:
            self.food_preference.remove(normalized)
            return True
        return False

    def load_from_dict(self, data: Dict[str, Any]) -> None:
        """Loads state from an existing dictionary."""
        if "intent" in data:
            self.set_field("intent", data["intent"])
        if "party_size" in data:
            self.set_field("party_size", data["party_size"])
        if "date" in data:
            self.set_field("date", data["date"])
        if "time" in data:
            self.set_field("time", data["time"])
        if "customer_name" in data:
            self.set_field("customer_name", data["customer_name"])
        if "booking_id" in data:
            self.set_field("booking_id", data["booking_id"])
        if "food_preference" in data:
            self.set_field("food_preference", data["food_preference"])

    def _check_negation_removals(self, message: str) -> None:
        """Inspects customer message for conversational removal signals."""
        msg_lower = message.lower()

        # Food preference removal check
        for pattern in FOOD_REMOVAL_PATTERNS:
            if re.search(pattern, msg_lower, re.IGNORECASE):
                self.food_preference = []
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
        5. Food preference: Appends new unique tags if provided.
        6. Removals: If the message requests removing/clearing fields, resets them.
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
            has_question = bool(re.search(r"\b(?:can you|could you|what|when|where|how|hours|time|menu|\?)\b", msg_lower))

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
        if new_party_size is not None:
            if self.party_size is not None and new_party_size != self.party_size and message:
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

                if has_explicit_party_change and not (is_dietary_mention and not re.search(r"\b(?:make\s+it|change\s+to|switch\s+to)\s+\d+\b", msg_lower)):
                    self.party_size = new_party_size
                # otherwise preserve current party_size
            else:
                self.party_size = new_party_size

        # 4. Update date (add / overwrite / keep)
        new_date = extracted.get("date")
        if new_date is not None:
            self.date = new_date

        # 5. Update time (add / overwrite / keep)
        new_time = extracted.get("time")
        if new_time is not None:
            self.time = new_time

        # 6. Update food preference (handle substitution vs addition)
        new_food = extracted.get("food_preference")
        if isinstance(new_food, list):
            msg_lower = message.lower() if message else ""
            is_replacement = bool(re.search(r"\b(?:actually|instead|change(?:\s+it|\s+that)?\s+to|make it|rather than)\b", msg_lower))
            is_addition = bool(re.search(r"\b(?:also|and|in addition|another|as well|plus|both)\b", msg_lower))

            if is_replacement and not is_addition and new_food:
                # Substitute/replace previous preferences
                self.food_preference = [str(x).strip().lower() for x in new_food if x and str(x).strip()]
            elif new_food:
                for item in new_food:
                    tag = str(item).strip().lower()
                    if tag and tag not in self.food_preference:
                        self.food_preference.append(tag)

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
