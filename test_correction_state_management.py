"""
Regression Test Suite for Multi-Turn Slot Corrections and Replacements.

Verifies:
1. vegetarian -> non-vegetarian
2. non-vegetarian -> vegetarian
3. 4 guests -> 6 guests
4. Saturday -> Sunday
5. 8 PM -> 8:30 PM
6. 3 vegetarian + 2 non-vegetarian -> 5 vegetarian
7. all vegetarian -> all non-vegetarian
8. explicit preference -> corrected explicit preference
9. correction using "actually"
10. correction using "sorry"
11. correction using "change it"
12. correction using "make it"
13. correction using "instead"
14. correction using "no, I want..."
15. multiple corrections across several turns
16. Rule 5 party size change (scaling 'all' preferences vs preserving explicit counts)
17. User's exact reported conversation flow
"""

import unittest
from state_manager import BookingState


class TestCorrectionStateManagement(unittest.TestCase):

    def test_case_1_vegetarian_to_non_vegetarian(self):
        """1. vegetarian -> non-vegetarian: previous vegetarian preference is removed."""
        state = BookingState()
        state.set_field("party_size", 5)
        state.set_field("food_preference", {"vegetarian": 5})

        state.apply_extraction({"food_preference": {"non_vegetarian": 5}}, message="non veg 5")
        self.assertEqual(state.food_preference, {"non_vegetarian": 5})
        self.assertNotIn("vegetarian", state.food_preference)

    def test_case_2_non_vegetarian_to_vegetarian(self):
        """2. non-vegetarian -> vegetarian: previous non-vegetarian preference is removed."""
        state = BookingState()
        state.set_field("party_size", 5)
        state.set_field("food_preference", {"non_vegetarian": 5})

        state.apply_extraction({"food_preference": {"vegetarian": 5}}, message="actually all vegetarian")
        self.assertEqual(state.food_preference, {"vegetarian": 5})
        self.assertNotIn("non_vegetarian", state.food_preference)

    def test_case_3_party_size_change_4_to_6(self):
        """3. 4 guests -> 6 guests: party size updates and retains other booking slots."""
        state = BookingState()
        state.set_field("party_size", 4)
        state.set_field("date", "2026-09-26")
        state.set_field("time", "20:00")

        state.apply_extraction({"party_size": 6}, message="actually 6 people")
        self.assertEqual(state.party_size, 6)
        self.assertEqual(state.date, "2026-09-26")
        self.assertEqual(state.time, "20:00")

    def test_case_4_date_change_saturday_to_sunday(self):
        """4. Saturday -> Sunday: date updates to the corrected day."""
        state = BookingState()
        state.set_field("party_size", 4)
        state.set_field("date", "2026-09-26")
        state.set_field("time", "20:00")

        state.apply_extraction({"date": "2026-09-27"}, message="actually Sunday")
        self.assertEqual(state.date, "2026-09-27")
        self.assertEqual(state.party_size, 4)
        self.assertEqual(state.time, "20:00")

    def test_case_5_time_change_8pm_to_830pm(self):
        """5. 8 PM -> 8:30 PM: time updates to the corrected time."""
        state = BookingState()
        state.set_field("party_size", 4)
        state.set_field("time", "20:00")

        state.apply_extraction({"time": "20:30"}, message="make it 8:30 PM")
        self.assertEqual(state.time, "20:30")
        self.assertEqual(state.party_size, 4)

    def test_case_6_mixed_to_full_vegetarian(self):
        """6. 3 vegetarian + 2 non-vegetarian -> 5 vegetarian: previous counts replaced."""
        state = BookingState()
        state.set_field("party_size", 5)
        state.set_field("food_preference", {"vegetarian": 3, "non_vegetarian": 2})

        state.apply_extraction({"food_preference": {"vegetarian": 5}}, message="all vegetarian instead")
        self.assertEqual(state.food_preference, {"vegetarian": 5})
        self.assertNotIn("non_vegetarian", state.food_preference)

    def test_case_7_all_vegetarian_to_all_non_vegetarian(self):
        """7. all vegetarian -> all non-vegetarian: entire food preference replaced."""
        state = BookingState()
        state.set_field("party_size", 5)
        state.set_field("food_preference", {"vegetarian": 5})

        state.apply_extraction({"food_preference": {"non_vegetarian": 5}}, message="all non-veg make it")
        self.assertEqual(state.food_preference, {"non_vegetarian": 5})
        self.assertNotIn("vegetarian", state.food_preference)

    def test_case_8_explicit_preference_to_corrected_explicit_preference(self):
        """8. explicit preference -> corrected explicit preference: counts replaced rather than accumulated."""
        state = BookingState()
        state.set_field("party_size", 5)
        state.set_field("food_preference", {"vegetarian": 3, "non_vegetarian": 2})

        # Correction changes distribution to 4 vegetarian and 1 non-vegetarian
        state.apply_extraction({"food_preference": {"vegetarian": 4, "non_vegetarian": 1}},
                               message="actually 4 vegetarian and 1 non-vegetarian")
        self.assertEqual(state.food_preference, {"vegetarian": 4, "non_vegetarian": 1})

    def test_case_9_correction_using_actually(self):
        """9. correction using 'actually': replaces slot."""
        state = BookingState()
        state.set_field("party_size", 4)
        state.apply_extraction({"party_size": 6}, message="Actually, 6 people.")
        self.assertEqual(state.party_size, 6)

    def test_case_10_correction_using_sorry(self):
        """10. correction using 'sorry': replaces slot."""
        state = BookingState()
        state.set_field("party_size", 5)
        state.set_field("food_preference", {"vegetarian": 5})

        state.apply_extraction({"food_preference": {"non_vegetarian": 5}}, message="sorry all non-veg")
        self.assertEqual(state.food_preference, {"non_vegetarian": 5})
        self.assertNotIn("vegetarian", state.food_preference)

    def test_case_11_correction_using_change_it(self):
        """11. correction using 'change it': replaces slot."""
        state = BookingState()
        state.set_field("party_size", 5)
        state.set_field("food_preference", {"vegetarian": 5})

        state.apply_extraction({"food_preference": {"non_vegetarian": 5}}, message="change it I want all non-vegetarian")
        self.assertEqual(state.food_preference, {"non_vegetarian": 5})
        self.assertNotIn("vegetarian", state.food_preference)

    def test_case_12_correction_using_make_it(self):
        """12. correction using 'make it': replaces slot."""
        state = BookingState()
        state.set_field("party_size", 4)
        state.set_field("time", "19:00")

        state.apply_extraction({"time": "20:30"}, message="make it 8:30 PM")
        self.assertEqual(state.time, "20:30")

    def test_case_13_correction_using_instead(self):
        """13. correction using 'instead': replaces slot."""
        state = BookingState()
        state.set_field("party_size", 2)
        state.set_field("food_preference", {"vegetarian": 2})

        state.apply_extraction({"food_preference": {"vegan": 2}}, message="vegan instead")
        self.assertEqual(state.food_preference, {"vegan": 2})
        self.assertNotIn("vegetarian", state.food_preference)

    def test_case_14_correction_using_no_i_want(self):
        """14. correction using 'no, I want...': replaces slot."""
        state = BookingState()
        state.set_field("party_size", 4)
        state.apply_extraction({"party_size": 8}, message="no, I want a table for 8")
        self.assertEqual(state.party_size, 8)

    def test_case_15_multiple_corrections_across_several_turns(self):
        """15. multiple corrections across several turns."""
        state = BookingState()

        # Turn 1: 4 people
        state.apply_extraction({"party_size": 4, "intent": "booking"}, message="Table for 4")
        self.assertEqual(state.party_size, 4)

        # Turn 2: Saturday at 7 PM
        state.apply_extraction({"date": "2026-09-26", "time": "19:00"}, message="This Saturday at 7 PM")
        self.assertEqual(state.date, "2026-09-26")
        self.assertEqual(state.time, "19:00")

        # Turn 3: Correction 1 - party size 6
        state.apply_extraction({"party_size": 6}, message="Actually make it 6 people")
        self.assertEqual(state.party_size, 6)
        self.assertEqual(state.date, "2026-09-26")

        # Turn 4: Add preference - all vegetarian
        state.apply_extraction({"food_preference": {"vegetarian": 6}}, message="all vegetarian")
        self.assertEqual(state.food_preference, {"vegetarian": 6})

        # Turn 5: Correction 2 - time to 8:30 PM
        state.apply_extraction({"time": "20:30"}, message="Could we do 8:30 PM instead?")
        self.assertEqual(state.time, "20:30")
        self.assertEqual(state.party_size, 6)

        # Turn 6: Correction 3 - change to non-veg
        state.apply_extraction({"food_preference": {"non_vegetarian": 6}}, message="sorry all non-veg")
        self.assertEqual(state.food_preference, {"non_vegetarian": 6})
        self.assertNotIn("vegetarian", state.food_preference)

    def test_case_16_rule_5_party_size_change_scaling(self):
        """16. Rule 5: 'all' preference scales with party size; explicit counts do not invent new guests."""
        # Subcase A: "all vegetarian" scales when party size changes from 5 to 7
        state_a = BookingState()
        state_a.set_field("party_size", 5)
        state_a.apply_extraction({"food_preference": {"vegetarian": 5}}, message="all vegetarian")
        self.assertEqual(state_a.food_preference, {"vegetarian": 5})

        state_a.apply_extraction({"party_size": 7}, message="actually 7 people")
        self.assertEqual(state_a.party_size, 7)
        self.assertEqual(state_a.food_preference, {"vegetarian": 7})

        # Subcase B: explicit "3 vegetarian and 2 non-vegetarian" does not invent remainder when party size becomes 7
        state_b = BookingState()
        state_b.set_field("party_size", 5)
        state_b.apply_extraction({"food_preference": {"vegetarian": 3, "non_vegetarian": 2}},
                                 message="3 vegetarian and 2 non-vegetarian")
        self.assertEqual(state_b.food_preference, {"vegetarian": 3, "non_vegetarian": 2})

        state_b.apply_extraction({"party_size": 7}, message="actually 7 people")
        self.assertEqual(state_b.party_size, 7)
        # Should preserve existing counts without inventing the extra 2 people's preferences
        self.assertEqual(state_b.food_preference, {"vegetarian": 3, "non_vegetarian": 2})

    def test_case_17_user_reported_exact_conversation(self):
        """17. Exact conversation from the user's issue report."""
        state = BookingState()

        # Turn 1: vegetarian 5 make it
        state.apply_extraction({"party_size": 5, "food_preference": {"vegetarian": 5}}, message="vegetarian 5 make it")
        self.assertEqual(state.party_size, 5)
        self.assertEqual(state.food_preference, {"vegetarian": 5})

        # Turn 2: all vegetarian
        state.apply_extraction({"food_preference": {"vegetarian": 5}}, message="all vegetarian")
        self.assertEqual(state.food_preference, {"vegetarian": 5})

        # Turn 3: non veg 5
        state.apply_extraction({"food_preference": {"non_vegetarian": 5}}, message="non veg 5")
        self.assertEqual(state.food_preference, {"non_vegetarian": 5})
        self.assertNotIn("vegetarian", state.food_preference)

        # Turn 4: all non-veg make it
        state.apply_extraction({"food_preference": {"non_vegetarian": 5}}, message="all non-veg make it")
        self.assertEqual(state.food_preference, {"non_vegetarian": 5})
        self.assertNotIn("vegetarian", state.food_preference)

        # Turn 5: sorry all non-veg
        state.apply_extraction({"food_preference": {"non_vegetarian": 5}}, message="sorry all non-veg")
        self.assertEqual(state.food_preference, {"non_vegetarian": 5})
        self.assertNotIn("vegetarian", state.food_preference)

        # Turn 6: change it I want all non-vegetarian
        state.apply_extraction({"food_preference": {"non_vegetarian": 5}}, message="change it I want all non-vegetarian")
        self.assertEqual(state.food_preference, {"non_vegetarian": 5})
        self.assertNotIn("vegetarian", state.food_preference)


class TestLiveLLMCorrections(unittest.TestCase):
    """End-to-end tests for corrections with update_booking_state_with_llm."""

    def test_llm_all_non_veg_replaces_vegetarian(self):
        """Live LLM: 'all non-veg make it' replaces 'vegetarian: 5' with 'non_vegetarian: 5'."""
        from intent_classifier import update_booking_state_with_llm
        initial_state = {
            "intent": "booking",
            "party_size": 5,
            "date": "2027-05-08",
            "time": None,
            "food_preference": {"vegetarian": 5}
        }
        res = update_booking_state_with_llm(initial_state, "all non-veg make it")
        self.assertEqual(res.get("party_size"), 5)
        self.assertEqual(res.get("food_preference"), {"non_vegetarian": 5})

    def test_llm_sorry_all_non_veg(self):
        """Live LLM: 'sorry all non-veg' replaces 'vegetarian: 5' with 'non_vegetarian: 5'."""
        from intent_classifier import update_booking_state_with_llm
        initial_state = {
            "intent": "booking",
            "party_size": 5,
            "date": "2027-05-08",
            "time": None,
            "food_preference": {"vegetarian": 5}
        }
        res = update_booking_state_with_llm(initial_state, "sorry all non-veg")
        self.assertEqual(res.get("party_size"), 5)
        self.assertEqual(res.get("food_preference"), {"non_vegetarian": 5})

    def test_llm_time_correction(self):
        """Live LLM: 'make it 8:30 PM' corrects time from 20:00 to 20:30."""
        from intent_classifier import update_booking_state_with_llm
        initial_state = {
            "intent": "booking",
            "party_size": 4,
            "date": "2026-09-19",
            "time": "20:00",
            "food_preference": {}
        }
        res = update_booking_state_with_llm(initial_state, "make it 8:30 PM")
        self.assertEqual(res.get("party_size"), 4)
        self.assertEqual(res.get("time"), "20:30")

    def test_llm_party_size_correction(self):
        """Live LLM: 'Actually, 6 people' corrects party_size from 4 to 6."""
        from intent_classifier import update_booking_state_with_llm
        initial_state = {
            "intent": "booking",
            "party_size": 4,
            "date": "2026-09-19",
            "time": "20:00",
            "food_preference": {}
        }
        res = update_booking_state_with_llm(initial_state, "Actually, 6 people")
        self.assertEqual(res.get("party_size"), 6)
        self.assertEqual(res.get("time"), "20:00")


if __name__ == "__main__":
    unittest.main()
