"""
Automated Test Suite for Preference Counting with Exact Person Counts.

Verifies:
1. Single-turn extraction for all preference categories:
   - Food preferences with partial party restrictions and non_vegetarian remainder.
   - Seating preferences preserving exact headcounts (not defaulting to full party).
   - Accessibility requirements with exact headcounts.
   - Multiple concurrent preferences with separate counts.
   - Full party preferences (all of us / everyone).
   - Unspecified preference counts (conventially set to null).
2. Multi-turn dialogue state tracking across turns:
   - Incremental preference addition.
   - Count updates across messages (1 vegetarian -> 2 vegetarian -> all vegetarian).
   - Removal / cancellation of preferences (no dietary requirements).
3. Logical consistency and recalculation on party size change (Rule 10):
   - Recalculating non_vegetarian when party size changes.
   - Clamping preference counts so they never exceed the updated party size.
"""

import unittest
from intent_classifier import normalize_booking_data, extract_booking_info, update_booking_state_with_llm
from state_manager import BookingState


class TestPreferenceCountingNormalization(unittest.TestCase):
    """Test Python-level validation and normalization of preference counts."""

    def test_example_1_food_partial(self):
        """Table for 5, 1 vegetarian -> vegetarian: 1, non_vegetarian: 4."""
        raw = {
            "intent": "booking",
            "party_size": 5,
            "date": None,
            "time": None,
            "food_preference": {"vegetarian": 1}
        }
        res = normalize_booking_data(raw)
        self.assertEqual(res["party_size"], 5)
        self.assertEqual(res["food_preference"], {"vegetarian": 1, "non_vegetarian": 4})

    def test_example_2_seating_partial(self):
        """Party of 6, 2 window -> seating_preference: {'window': 2} (must NOT be 6)."""
        raw = {
            "intent": "booking",
            "party_size": 6,
            "date": None,
            "time": None,
            "seating_preference": {"window": 2}
        }
        res = normalize_booking_data(raw)
        self.assertEqual(res["party_size"], 6)
        self.assertEqual(res["seating_preference"], {"window": 2})

    def test_example_3_accessibility_partial(self):
        """Party of 5, 1 wheelchair -> accessibility_requirement: {'wheelchair_access': 1}."""
        raw = {
            "intent": "booking",
            "party_size": 5,
            "date": None,
            "time": None,
            "accessibility_requirement": {"wheelchair_access": 1}
        }
        res = normalize_booking_data(raw)
        self.assertEqual(res["party_size"], 5)
        self.assertEqual(res["accessibility_requirement"], {"wheelchair_access": 1})

    def test_example_4_multiple_preferences(self):
        """Party of 6, 2 vegetarian, 1 wheelchair, 3 window."""
        raw = {
            "intent": "booking",
            "party_size": 6,
            "date": None,
            "time": None,
            "food_preference": {"vegetarian": 2},
            "accessibility_requirement": {"wheelchair_access": 1},
            "seating_preference": {"window": 3}
        }
        res = normalize_booking_data(raw)
        self.assertEqual(res["party_size"], 6)
        self.assertEqual(res["food_preference"], {"vegetarian": 2, "non_vegetarian": 4})
        self.assertEqual(res["accessibility_requirement"], {"wheelchair_access": 1})
        self.assertEqual(res["seating_preference"], {"window": 3})

    def test_full_party_food_preference(self):
        """Party of 5, all 5 vegetarian -> vegetarian: 5, non_vegetarian omitted."""
        raw = {
            "intent": "booking",
            "party_size": 5,
            "date": None,
            "time": None,
            "food_preference": {"vegetarian": 5}
        }
        res = normalize_booking_data(raw)
        self.assertEqual(res["party_size"], 5)
        self.assertEqual(res["food_preference"], {"vegetarian": 5})
        self.assertNotIn("non_vegetarian", res["food_preference"])

    def test_unspecified_preference_count(self):
        """Unspecified count defaults to null (None in Python)."""
        raw = {
            "intent": "booking",
            "party_size": 4,
            "date": None,
            "time": None,
            "seating_preference": {"window": None}
        }
        res = normalize_booking_data(raw)
        self.assertEqual(res["seating_preference"], {"window": None})

    def test_party_size_clamping(self):
        """Preference count cannot exceed party size (Rule 10)."""
        raw = {
            "intent": "booking",
            "party_size": 3,
            "date": None,
            "time": None,
            "seating_preference": {"window": 5},
            "food_preference": {"vegetarian": 4}
        }
        res = normalize_booking_data(raw)
        self.assertEqual(res["seating_preference"]["window"], 3)
        self.assertEqual(res["food_preference"]["vegetarian"], 3)
        self.assertNotIn("non_vegetarian", res["food_preference"])


class TestStateManagementPreferenceCounting(unittest.TestCase):
    """Test BookingState logic for preference counts across multi-turn interactions."""

    def test_party_size_change_recalculates_food_preference(self):
        """When party size decreases, non_vegetarian is recalculated against latest party size."""
        state = BookingState()
        state.set_field("party_size", 5)
        state.set_field("food_preference", {"vegetarian": 2, "non_vegetarian": 3})

        # Customer changes party size to 4
        state.apply_extraction({"party_size": 4}, message="Actually make it 4 people.")
        self.assertEqual(state.party_size, 4)
        self.assertEqual(state.food_preference["vegetarian"], 2)
        self.assertEqual(state.food_preference["non_vegetarian"], 2)

    def test_party_size_decrease_clamps_impossible_counts(self):
        """When party size decreases below preference count, clamp to new party size."""
        state = BookingState()
        state.set_field("party_size", 6)
        state.set_field("food_preference", {"vegetarian": 4, "non_vegetarian": 2})
        state.set_field("seating_preference", {"window": 5})

        # Party size decreases to 3
        state.apply_extraction({"party_size": 3}, message="Change to 3 people.")
        self.assertEqual(state.party_size, 3)
        self.assertEqual(state.food_preference["vegetarian"], 3)
        self.assertNotIn("non_vegetarian", state.food_preference)
        self.assertEqual(state.seating_preference["window"], 3)

    def test_conversational_removal_of_seating_and_dietary(self):
        """Test conversational removals for preferences."""
        state = BookingState()
        state.set_field("party_size", 4)
        state.set_field("food_preference", {"vegetarian": 1, "non_vegetarian": 3})
        state.set_field("seating_preference", {"window": 2})
        state.set_field("accessibility_requirement", {"wheelchair_access": 1})

        # Remove seating
        state.apply_extraction({}, message="Never mind the window seating, any table is fine.")
        self.assertEqual(state.seating_preference, {})
        self.assertEqual(state.food_preference["vegetarian"], 1)

        # Remove dietary
        state.apply_extraction({}, message="Actually, no dietary requirements.")
        self.assertEqual(state.food_preference, {})

        # Remove accessibility
        state.apply_extraction({}, message="We don't need wheelchair access anymore.")
        self.assertEqual(state.accessibility_requirement, {})


class TestLiveLLMPreferenceCounting(unittest.TestCase):
    """End-to-end tests querying the LLM with the updated extraction & DST prompts."""

    def test_llm_example_1_food(self):
        """Input: 'Table for 5. One person is vegetarian.'"""
        res = extract_booking_info("Table for 5. One person is vegetarian.")
        self.assertEqual(res.get("party_size"), 5)
        food = res.get("food_preference", {})
        self.assertEqual(food.get("vegetarian"), 1)
        self.assertEqual(food.get("non_vegetarian"), 4)

    def test_llm_example_2_seating(self):
        """Input: 'We are 6 people. Two of us would like window seating.'"""
        res = extract_booking_info("We are 6 people. Two of us would like window seating.")
        self.assertEqual(res.get("party_size"), 6)
        seating = res.get("seating_preference", {})
        self.assertEqual(seating.get("window"), 2)

    def test_llm_example_3_accessibility(self):
        """Input: 'There will be 5 of us, but one guest uses a wheelchair.'"""
        res = extract_booking_info("There will be 5 of us, but one guest uses a wheelchair.")
        self.assertEqual(res.get("party_size"), 5)
        acc = res.get("accessibility_requirement", {})
        self.assertEqual(acc.get("wheelchair_access"), 1)

    def test_llm_example_4_multiple_preferences(self):
        """Input: 'We are 6 people. Two are vegetarian, one needs wheelchair access, and three would prefer a window table.'"""
        res = extract_booking_info("We are 6 people. Two are vegetarian, one needs wheelchair access, and three would prefer a window table.")
        self.assertEqual(res.get("party_size"), 6)
        self.assertEqual(res.get("food_preference", {}).get("vegetarian"), 2)
        self.assertEqual(res.get("food_preference", {}).get("non_vegetarian"), 4)
        self.assertEqual(res.get("accessibility_requirement", {}).get("wheelchair_access"), 1)
        self.assertEqual(res.get("seating_preference", {}).get("window"), 3)

    def test_llm_multi_turn_conversation_changes(self):
        """
        Customer: 'We are 5 people. One person is vegetarian.'
        State: party_size: 5, vegetarian: 1, non_vegetarian: 4
        Customer: 'Actually, two people are vegetarian.'
        Updated state: party_size: 5, vegetarian: 2, non_vegetarian: 3
        Customer: 'Actually, all of us are vegetarian.'
        Updated state: party_size: 5, vegetarian: 5
        """
        session = BookingState()

        t1 = session.process_message("We are 5 people. One person is vegetarian.")
        self.assertEqual(t1.get("party_size"), 5)
        self.assertEqual(t1.get("food_preference", {}).get("vegetarian"), 1)
        self.assertEqual(t1.get("food_preference", {}).get("non_vegetarian"), 4)

        t2 = session.process_message("Actually, two people are vegetarian.")
        self.assertEqual(t2.get("party_size"), 5)
        self.assertEqual(t2.get("food_preference", {}).get("vegetarian"), 2)
        self.assertEqual(t2.get("food_preference", {}).get("non_vegetarian"), 3)

        t3 = session.process_message("Actually, all of us are vegetarian.")
        self.assertEqual(t3.get("party_size"), 5)
        self.assertEqual(t3.get("food_preference", {}).get("vegetarian"), 5)
        self.assertNotIn("non_vegetarian", t3.get("food_preference", {}))


if __name__ == "__main__":
    unittest.main()
