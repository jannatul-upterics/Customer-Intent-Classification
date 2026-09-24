"""
Test Suite for Automatic Party Size Inference from Food Preference Counts.

Covers:
1. Party-size inference when party_size is null and explicit food-preference counts are provided:
   - veg 2 -> party_size = 2
   - 2 veg -> party_size = 2
   - vegetarian for 3 -> party_size = 3
   - non veg 4 -> party_size = 4
   - 4 non vegetarian -> party_size = 4
   - 2 vegetarian and 3 non-vegetarian -> party_size = 5
   - 3 veg + 2 non veg -> party_size = 5
2. Priority rule:
   - If customer explicitly provides total party size, that value MUST take priority:
   - 5 people, 2 vegetarian -> party_size = 5
   - there will be 6 people, 2 are vegetarian -> party_size = 6, {"vegetarian": 2, "non_vegetarian": 4}
3. Multi-turn dialogue state tracking:
   - Turn 1: hi book a table -> party_size: null
   - Turn 2: veg 2 -> party_size: 2, vegetarian: 2
   - Turn 3: no make it non veg -> party_size: 2, non_vegetarian: 2 (existing correction logic preserved!)
"""

import unittest
import os
from intent_classifier import (
    normalize_booking_data,
    extract_booking_info,
    update_booking_state_with_llm,
    extract_explicit_party_size,
    extract_food_preference_counts,
)
from state_manager import BookingState


class TestExplicitPartySizeHelper(unittest.TestCase):
    """Test helper that extracts explicit total party size."""

    def test_explicit_phrases(self):
        self.assertEqual(extract_explicit_party_size("there will be 6 people, 2 are vegetarian"), 6)
        self.assertEqual(extract_explicit_party_size("5 people, 2 vegetarian"), 5)
        self.assertEqual(extract_explicit_party_size("table for 4"), 4)
        self.assertEqual(extract_explicit_party_size("party of 5"), 5)
        self.assertEqual(extract_explicit_party_size("booth for 3 people"), 3)
        self.assertEqual(extract_explicit_party_size("make that 8 people"), 8)

    def test_food_only_phrases_return_none(self):
        self.assertIsNone(extract_explicit_party_size("veg 2"))
        self.assertIsNone(extract_explicit_party_size("2 veg"))
        self.assertIsNone(extract_explicit_party_size("vegetarian for 3"))
        self.assertIsNone(extract_explicit_party_size("non veg 4"))
        self.assertIsNone(extract_explicit_party_size("4 non vegetarian"))
        self.assertIsNone(extract_explicit_party_size("2 vegetarian and 3 non-vegetarian"))
        self.assertIsNone(extract_explicit_party_size("3 veg + 2 non veg"))


class TestFoodPreferenceCountsHelper(unittest.TestCase):
    """Test helper that extracts food preference counts."""

    def test_food_preference_counts(self):
        self.assertEqual(extract_food_preference_counts("veg 2"), {"vegetarian": 2})
        self.assertEqual(extract_food_preference_counts("2 veg"), {"vegetarian": 2})
        self.assertEqual(extract_food_preference_counts("vegetarian for 3"), {"vegetarian": 3})
        self.assertEqual(extract_food_preference_counts("non veg 4"), {"non_vegetarian": 4})
        self.assertEqual(extract_food_preference_counts("4 non vegetarian"), {"non_vegetarian": 4})
        self.assertEqual(extract_food_preference_counts("2 vegetarian and 3 non-vegetarian"), {"vegetarian": 2, "non_vegetarian": 3})
        self.assertEqual(extract_food_preference_counts("3 veg + 2 non veg"), {"vegetarian": 3, "non_vegetarian": 2})


class TestPartySizeInferenceNormalization(unittest.TestCase):
    """Test party-size inference inside normalize_booking_data."""

    def test_veg_2(self):
        raw = {"intent": "booking", "party_size": None, "date": None, "time": None, "food_preference": {"vegetarian": 2}}
        res = normalize_booking_data(raw, message="veg 2")
        self.assertEqual(res["party_size"], 2)
        self.assertEqual(res["food_preference"], {"vegetarian": 2})

    def test_2_veg(self):
        raw = {"intent": "booking", "party_size": None, "date": None, "time": None, "food_preference": {"vegetarian": 2}}
        res = normalize_booking_data(raw, message="2 veg")
        self.assertEqual(res["party_size"], 2)
        self.assertEqual(res["food_preference"], {"vegetarian": 2})

    def test_vegetarian_for_3(self):
        raw = {"intent": "booking", "party_size": None, "date": None, "time": None, "food_preference": {"vegetarian": 3}}
        res = normalize_booking_data(raw, message="vegetarian for 3")
        self.assertEqual(res["party_size"], 3)
        self.assertEqual(res["food_preference"], {"vegetarian": 3})

    def test_non_veg_4(self):
        raw = {"intent": "booking", "party_size": None, "date": None, "time": None, "food_preference": {"non_vegetarian": 4}}
        res = normalize_booking_data(raw, message="non veg 4")
        self.assertEqual(res["party_size"], 4)
        self.assertEqual(res["food_preference"], {"non_vegetarian": 4})

    def test_4_non_vegetarian(self):
        raw = {"intent": "booking", "party_size": None, "date": None, "time": None, "food_preference": {"non_vegetarian": 4}}
        res = normalize_booking_data(raw, message="4 non vegetarian")
        self.assertEqual(res["party_size"], 4)
        self.assertEqual(res["food_preference"], {"non_vegetarian": 4})

    def test_2_veg_and_3_non_veg(self):
        raw = {"intent": "booking", "party_size": None, "date": None, "time": None, "food_preference": {"vegetarian": 2, "non_vegetarian": 3}}
        res = normalize_booking_data(raw, message="2 vegetarian and 3 non-vegetarian")
        self.assertEqual(res["party_size"], 5)
        self.assertEqual(res["food_preference"], {"vegetarian": 2, "non_vegetarian": 3})

    def test_3_veg_plus_2_non_veg(self):
        raw = {"intent": "booking", "party_size": None, "date": None, "time": None, "food_preference": {"vegetarian": 3, "non_vegetarian": 2}}
        res = normalize_booking_data(raw, message="3 veg + 2 non veg")
        self.assertEqual(res["party_size"], 5)
        self.assertEqual(res["food_preference"], {"vegetarian": 3, "non_vegetarian": 2})

    def test_priority_rule_5_people_2_veg(self):
        """Customer explicitly says 5 people -> party_size must remain 5, not 2."""
        raw = {"intent": "booking", "party_size": 5, "date": None, "time": None, "food_preference": {"vegetarian": 2}}
        res = normalize_booking_data(raw, message="5 people, 2 vegetarian")
        self.assertEqual(res["party_size"], 5)
        self.assertEqual(res["food_preference"], {"vegetarian": 2})

    def test_priority_rule_6_people_2_veg(self):
        """Customer explicitly says 6 people -> party_size must remain 6, not 2."""
        raw = {"intent": "booking", "party_size": 6, "date": None, "time": None, "food_preference": {"vegetarian": 2, "non_vegetarian": 4}}
        res = normalize_booking_data(raw, message="there will be 6 people, 2 are vegetarian")
        self.assertEqual(res["party_size"], 6)
        self.assertEqual(res["food_preference"], {"vegetarian": 2, "non_vegetarian": 4})


class TestPartySizeInferenceStateManager(unittest.TestCase):
    """Test party-size inference with BookingState apply_extraction."""

    def test_state_manager_multi_turn_user_flow(self):
        """
        Turn 1: Customer: hi book a table -> party_size: null
        Turn 2: Customer: veg 2 -> party_size: 2, vegetarian: 2
        Turn 3: Customer: no make it non veg -> party_size: 2, non_vegetarian: 2
        """
        state = BookingState()
        s1 = state.apply_extraction({"intent": "booking", "party_size": None, "date": None, "time": None, "food_preference": {}}, message="hi book a table")
        self.assertIsNone(s1["party_size"])
        self.assertFalse(s1["food_preference"])

        s2 = state.apply_extraction({"intent": "booking", "party_size": None, "date": None, "time": None, "food_preference": {"vegetarian": 2}}, message="veg 2")
        self.assertEqual(s2["party_size"], 2)
        self.assertEqual(s2["food_preference"], {"vegetarian": 2})

        s3 = state.apply_extraction({"intent": "booking", "party_size": None, "date": None, "time": None, "food_preference": {"non_vegetarian": 2}}, message="no make it non veg")
        self.assertEqual(s3["party_size"], 2)
        self.assertEqual(s3["food_preference"], {"non_vegetarian": 2})

    def test_state_manager_multi_food_sum(self):
        """2 vegetarian and 3 non-vegetarian -> party_size = 5."""
        state = BookingState()
        s1 = state.apply_extraction(
            {"intent": "booking", "party_size": None, "date": None, "time": None, "food_preference": {"vegetarian": 2, "non_vegetarian": 3}},
            message="2 vegetarian and 3 non-vegetarian"
        )
        self.assertEqual(s1["party_size"], 5)
        self.assertEqual(s1["food_preference"], {"vegetarian": 2, "non_vegetarian": 3})

    def test_state_manager_priority_rule(self):
        """Explicit party size takes priority over food counts."""
        state = BookingState()
        s1 = state.apply_extraction(
            {"intent": "booking", "party_size": 6, "date": None, "time": None, "food_preference": {"vegetarian": 2}},
            message="there will be 6 people, 2 are vegetarian"
        )
        self.assertEqual(s1["party_size"], 6)


class TestLiveLLMPartySizeInference(unittest.TestCase):
    """End-to-end live LLM tests for party size inference."""

    @classmethod
    def setUpClass(cls):
        if not os.environ.get("GROQ_API_KEY"):
            raise unittest.SkipTest("GROQ_API_KEY not set")

    def test_live_user_conversation_flow(self):
        """Verify the exact sequence from the user's issue description."""
        b = BookingState()

        # Turn 1
        s1 = b.process_message("hi book a table")
        self.assertEqual(s1["intent"], "booking")
        self.assertIsNone(s1["party_size"])

        # Turn 2
        s2 = b.process_message("veg 2")
        self.assertEqual(s2["intent"], "booking")
        self.assertEqual(s2["party_size"], 2)
        self.assertEqual(s2["food_preference"].get("vegetarian"), 2)

        # Turn 3
        s3 = b.process_message("no make it non veg")
        self.assertEqual(s3["intent"], "booking")
        self.assertEqual(s3["party_size"], 2)
        self.assertEqual(s3["food_preference"].get("non_vegetarian"), 2)
        self.assertNotIn("vegetarian", s3["food_preference"])

    def test_live_priority_rule_6_people(self):
        """Customer: there will be 6 people, 2 are vegetarian -> party_size=6."""
        b = BookingState()
        res = b.process_message("there will be 6 people, 2 are vegetarian")
        self.assertEqual(res["party_size"], 6)
        self.assertEqual(res["food_preference"].get("vegetarian"), 2)

    def test_live_priority_rule_5_people(self):
        """Customer: 5 people, 2 vegetarian -> party_size=5."""
        b = BookingState()
        res = b.process_message("5 people, 2 vegetarian")
        self.assertEqual(res["party_size"], 5)
        self.assertEqual(res["food_preference"].get("vegetarian"), 2)

    def test_live_combined_counts_sum(self):
        """Customer: 2 vegetarian and 3 non-vegetarian -> party_size=5."""
        b = BookingState()
        res = b.process_message("2 vegetarian and 3 non-vegetarian")
        self.assertEqual(res["party_size"], 5)
        self.assertEqual(res["food_preference"].get("vegetarian"), 2)
        self.assertEqual(res["food_preference"].get("non_vegetarian"), 3)


if __name__ == "__main__":
    unittest.main()
