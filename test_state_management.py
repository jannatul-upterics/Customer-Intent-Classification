"""
Automated Test Suite for Conversation State Management.

Tests:
1. Adding information across multi-turn messages
2. Updating existing information (e.g. party size 4 -> 6)
3. Removing information (conversational and programmatic)
4. Keeping information previously provided
5. Changing customer intent (booking -> modification -> cancellation)
6. Exact end-to-end conversation flows
"""

import unittest
from state_manager import BookingState


class TestConversationStateManagement(unittest.TestCase):

    def setUp(self):
        """Create a fresh BookingState instance for each test."""
        self.state = BookingState()

    def test_initial_state(self):
        """Test default initial state matches the canonical 5-field schema."""
        expected = {
            "intent": "booking",
            "party_size": None,
            "date": None,
            "time": None,
            "food_preference": []
        }
        self.assertEqual(self.state.to_dict(), expected)

    def test_adding_information_step_by_step(self):
        """Test incrementally adding information across multiple turns."""
        # Turn 1: Add party size
        turn1_extracted = {
            "intent": "booking",
            "party_size": 4,
            "date": None,
            "time": None,
            "food_preference": []
        }
        state1 = self.state.apply_extraction(turn1_extracted, message="I need a table for 4.")
        self.assertEqual(state1["party_size"], 4)
        self.assertIsNone(state1["date"])
        self.assertIsNone(state1["time"])
        self.assertEqual(state1["food_preference"], [])

        # Turn 2: Add date and time
        turn2_extracted = {
            "intent": "booking",
            "party_size": None,
            "date": "Saturday",
            "time": "20:00",
            "food_preference": []
        }
        state2 = self.state.apply_extraction(turn2_extracted, message="This Saturday at 8 PM.")
        # Party size must be KEPT from Turn 1
        self.assertEqual(state2["party_size"], 4)
        # Date and time must be ADDED
        self.assertEqual(state2["date"], "Saturday")
        self.assertEqual(state2["time"], "20:00")

        # Turn 3: Add dietary preference
        turn3_extracted = {
            "intent": "booking",
            "party_size": None,
            "date": None,
            "time": None,
            "food_preference": ["vegetarian"]
        }
        state3 = self.state.apply_extraction(turn3_extracted, message="One person is vegetarian.")
        self.assertEqual(state3["party_size"], 4)
        self.assertEqual(state3["date"], "Saturday")
        self.assertEqual(state3["time"], "20:00")
        self.assertEqual(state3["food_preference"], ["vegetarian"])

    def test_updating_existing_information(self):
        """Test updating/overwriting previously provided information."""
        # Setup: table for 4 on Saturday at 20:00
        self.state.apply_extraction({
            "intent": "booking",
            "party_size": 4,
            "date": "Saturday",
            "time": "20:00",
            "food_preference": []
        })

        # Update party size: "Actually, make it 6."
        update_extraction = {
            "intent": "booking",
            "party_size": 6,
            "date": None,
            "time": None,
            "food_preference": []
        }
        updated_state = self.state.apply_extraction(update_extraction, message="Actually, make it 6.")
        self.assertEqual(updated_state["party_size"], 6)
        # Verify other fields remain unchanged
        self.assertEqual(updated_state["date"], "Saturday")
        self.assertEqual(updated_state["time"], "20:00")

        # Update time: "Could we do 9 PM instead?"
        time_update = {
            "intent": "modification",
            "party_size": None,
            "date": None,
            "time": "21:00",
            "food_preference": []
        }
        updated_time_state = self.state.apply_extraction(time_update, message="Could we do 9 PM instead?")
        self.assertEqual(updated_time_state["party_size"], 6)
        self.assertEqual(updated_time_state["date"], "Saturday")
        self.assertEqual(updated_time_state["time"], "21:00")

    def test_keeping_information(self):
        """Test that missing/null values in new extraction do not wipe existing state."""
        self.state.set_field("party_size", 5)
        self.state.set_field("date", "Friday")
        self.state.set_field("time", "19:00")
        self.state.set_field("food_preference", ["vegan"])

        # Customer sends inquiry or chit-chat that extracts no new booking parameters
        inquiry_extraction = {
            "intent": "inquiry",
            "party_size": None,
            "date": None,
            "time": None,
            "food_preference": []
        }
        res = self.state.apply_extraction(inquiry_extraction, message="Do you have outdoor seating?")
        self.assertEqual(res["intent"], "inquiry")
        self.assertEqual(res["party_size"], 5)
        self.assertEqual(res["date"], "Friday")
        self.assertEqual(res["time"], "19:00")
        self.assertEqual(res["food_preference"], ["vegan"])

    def test_removing_information_programmatically(self):
        """Test programmatic field removals and item removals."""
        self.state.set_field("party_size", 4)
        self.state.set_field("date", "Saturday")
        self.state.set_field("time", "20:00")
        self.state.set_field("food_preference", ["vegan", "nut-free"])

        # Remove single dietary preference
        removed = self.state.remove_dietary_preference("vegan")
        self.assertTrue(removed)
        self.assertEqual(self.state.to_dict()["food_preference"], ["nut-free"])

        # Remove field: time
        self.state.remove_field("time")
        self.assertIsNone(self.state.to_dict()["time"])

        # Remove field: food_preference
        self.state.remove_field("food_preference")
        self.assertEqual(self.state.to_dict()["food_preference"], [])

        # Check remaining fields untouched
        self.assertEqual(self.state.to_dict()["party_size"], 4)
        self.assertEqual(self.state.to_dict()["date"], "Saturday")

    def test_removing_information_conversationally(self):
        """Test conversational removals (e.g. 'no allergies', 'never mind the date')."""
        self.state.set_field("food_preference", ["gluten-free", "dairy-free"])
        self.state.set_field("date", "Friday")
        self.state.set_field("party_size", 4)

        # Turn: customer negates allergies
        extraction = {
            "intent": "booking",
            "party_size": None,
            "date": None,
            "time": None,
            "food_preference": []
        }
        state = self.state.apply_extraction(extraction, message="Actually, no dietary requirements or allergies.")
        self.assertEqual(state["food_preference"], [])
        self.assertEqual(state["party_size"], 4)
        self.assertEqual(state["date"], "Friday")

        # Turn: customer removes date
        state = self.state.apply_extraction(extraction, message="Never mind the date, any day is fine.")
        self.assertIsNone(state["date"])
        self.assertEqual(state["party_size"], 4)

    def test_changing_intent(self):
        """Test customer changing intent across conversation turns."""
        # Initial intent: booking
        self.assertEqual(self.state.intent, "booking")

        # Turn 1: customer asks question -> inquiry
        self.state.apply_extraction({
            "intent": "inquiry",
            "party_size": None,
            "date": None,
            "time": None,
            "food_preference": []
        }, message="Do you have parking available?")
        self.assertEqual(self.state.intent, "inquiry")

        # Turn 2: customer decides to book -> booking
        self.state.apply_extraction({
            "intent": "booking",
            "party_size": 2,
            "date": "Friday",
            "time": "19:00",
            "food_preference": []
        }, message="Great, book a table for two this Friday at 7 PM.")
        self.assertEqual(self.state.intent, "booking")
        self.assertEqual(self.state.party_size, 2)

        # Turn 3: customer cancels -> cancellation
        self.state.apply_extraction({
            "intent": "cancellation",
            "party_size": None,
            "date": None,
            "time": None,
            "food_preference": []
        }, message="Sorry, please cancel the reservation.")
        self.assertEqual(self.state.intent, "cancellation")
        # Existing parameters remain attached to the cancellation context
        self.assertEqual(self.state.party_size, 2)
        self.assertEqual(self.state.date, "Friday")

    def test_user_example_flow(self):
        """
        Verify the exact sequence from the user's prompt:
        Message 1: 'I'd like a table for 4.' -> party_size: 4
        Message 2: 'This Saturday at 8 PM.' -> party_size: 4, date: Saturday, time: 20:00
        Message 3: 'Actually, make it 6.' -> party_size: 6, date: Saturday, time: 20:00
        """
        state = BookingState()

        # Message 1
        m1_extracted = {
            "intent": "booking",
            "party_size": 4,
            "date": None,
            "time": None,
            "food_preference": []
        }
        s1 = state.apply_extraction(m1_extracted, message="I'd like a table for 4.")
        self.assertEqual(s1, {
            "intent": "booking",
            "party_size": 4,
            "date": None,
            "time": None,
            "food_preference": []
        })

        # Message 2
        m2_extracted = {
            "intent": "booking",
            "party_size": None,
            "date": "Saturday",
            "time": "20:00",
            "food_preference": []
        }
        s2 = state.apply_extraction(m2_extracted, message="This Saturday at 8 PM.")
        self.assertEqual(s2, {
            "intent": "booking",
            "party_size": 4,
            "date": "Saturday",
            "time": "20:00",
            "food_preference": []
        })

        # Message 3
        m3_extracted = {
            "intent": "booking",
            "party_size": 6,
            "date": None,
            "time": None,
            "food_preference": []
        }
        s3 = state.apply_extraction(m3_extracted, message="Actually, make it 6.")
        self.assertEqual(s3, {
            "intent": "booking",
            "party_size": 6,
            "date": "Saturday",
            "time": "20:00",
            "food_preference": []
        })

    def test_reset_functionality(self):
        """Test resetting state returns to default and wipes history."""
        self.state.set_field("party_size", 4)
        self.state.set_field("date", "Sunday")
        self.state.set_field("food_preference", ["vegan"])
        self.state.apply_extraction({"intent": "booking"}, message="test")

        reset_result = self.state.reset()
        self.assertEqual(reset_result, {
            "intent": "booking",
            "party_size": None,
            "date": None,
            "time": None,
            "food_preference": []
        })
        self.assertEqual(len(self.state.history), 0)

    def test_llm_state_update_examples(self):
        """
        Verify update_booking_state_with_llm on the user's specific examples:
        1. Updating party size from 4 to 6 on 'Actually, make it 6.'
        2. Adding vegetarian to food_preference on 'One person is vegetarian.'
        """
        from intent_classifier import update_booking_state_with_llm
        initial_state = {
            "intent": "booking",
            "party_size": 4,
            "date": "Saturday",
            "time": "20:00",
            "food_preference": []
        }

        # Example 1: Actually, make it 6.
        updated_1 = update_booking_state_with_llm(initial_state, "Actually, make it 6.")
        self.assertEqual(updated_1.get("party_size"), 6)
        self.assertEqual(updated_1.get("date"), "Saturday")
        self.assertEqual(updated_1.get("time"), "20:00")
        self.assertEqual(updated_1.get("food_preference"), [])

        # Example 2: One person is vegetarian.
        updated_2 = update_booking_state_with_llm(initial_state, "One person is vegetarian.")
        self.assertEqual(updated_2.get("party_size"), 4)
        self.assertEqual(updated_2.get("date"), "Saturday")
        self.assertEqual(updated_2.get("time"), "20:00")
        self.assertIn("vegetarian", updated_2.get("food_preference", []))

    def test_removing_requirement_flow(self):
        """Test removing a requirement: 'One person is vegetarian.' -> 'Actually, no dietary requirements.'"""
        state = BookingState()
        s1 = state.process_message("One person is vegetarian.")
        self.assertIn("vegetarian", s1["food_preference"])

        s2 = state.process_message("Actually, no dietary requirements.")
        self.assertEqual(s2["food_preference"], [])

    def test_changing_requirement_substitution(self):
        """Test requirement substitution: 'I need a vegetarian option.' -> 'Actually, make it vegan.'"""
        state = BookingState()
        s1 = state.process_message("I need a vegetarian option.")
        self.assertIn("vegetarian", s1["food_preference"])

        s2 = state.process_message("Actually, make it vegan.")
        self.assertEqual(s2["food_preference"], ["vegan"])

    def test_changing_multiple_booking_details(self):
        """Test multiple updates: 'Book for 4 people at 7 PM.' -> 'Actually, make it 6 people at 8 PM.'"""
        state = BookingState()
        s1 = state.process_message("Book for 4 people at 7 PM.")
        self.assertEqual(s1["party_size"], 4)
        self.assertEqual(s1["time"], "19:00")

        s2 = state.process_message("Actually, make it 6 people at 8 PM.")
        self.assertEqual(s2["party_size"], 6)
        self.assertEqual(s2["time"], "20:00")

    def test_changing_intention_completely(self):
        """Test intent pivot: 'I'd like to book a table for 4.' -> 'Actually, I don't want to book anymore. Can you tell me the restaurant's opening hours?'"""
        state = BookingState()
        s1 = state.process_message("I'd like a table for 4.")
        self.assertEqual(s1["intent"], "booking")

        s2 = state.process_message("Actually, I don't want to book anymore. Can you tell me the restaurant's opening hours?")
        self.assertEqual(s2["intent"], "inquiry")


    def test_party_size_not_changed_on_colleague_dietary_mention(self):
        """
        CONV-005 verification:
        Ensure party_size remains 3 when customer mentions colleague dietary requirements:
        1. 'I'd like to book a booth for 3 people this Sunday at 1:00 PM.'
        2. 'Oh, almost forgot! My colleague has a severe peanut allergy.'
        3. 'And another colleague is vegetarian.'
        Expected party_size: 3.
        """
        state = BookingState()
        s1 = state.process_message("I'd like to book a booth for 3 people this Sunday at 1:00 PM.")
        self.assertEqual(s1["party_size"], 3)
        self.assertEqual(s1["date"], "Sunday")
        self.assertEqual(s1["time"], "13:00")
        self.assertEqual(s1["food_preference"], [])

        s2 = state.process_message("Oh, almost forgot! My colleague has a severe peanut allergy.")
        self.assertEqual(s2["party_size"], 3)
        self.assertIn("nut-free", s2["food_preference"])

        s3 = state.process_message("And another colleague is vegetarian.")
        self.assertEqual(s3["party_size"], 3)
        self.assertIn("nut-free", s3["food_preference"])
        self.assertIn("vegetarian", s3["food_preference"])


if __name__ == "__main__":
    unittest.main()
