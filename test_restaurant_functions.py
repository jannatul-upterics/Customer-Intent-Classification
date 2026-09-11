"""
Tests for Restaurant Booking Functions.

Tests the four core functions independently:
1. check_availability
2. create_booking
3. modify_booking
4. cancel_booking
"""

import json
import unittest
from restaurant_functions import (
    check_availability,
    create_booking,
    modify_booking,
    cancel_booking
)


class TestRestaurantFunctions(unittest.TestCase):

    def test_check_availability(self):
        """Test checking availability with date, time, and party size."""
        result = check_availability(date="Saturday", time="20:00", party_size=4)

        self.assertTrue(result["success"])
        self.assertEqual(result["action"], "check_availability")
        self.assertEqual(result["date"], "Saturday")
        self.assertEqual(result["time"], "20:00")
        self.assertEqual(result["party_size"], 4)
        self.assertTrue(result["available"])
        print("\n[TEST] check_availability output:")
        print(json.dumps(result, indent=2))

    def test_create_booking(self):
        """Test creating a booking with customer name, date, time, and party size."""
        result = create_booking(
            customer_name="John Doe",
            date="Friday",
            time="19:30",
            party_size=2
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["action"], "create_booking")
        self.assertEqual(result["customer_name"], "John Doe")
        self.assertEqual(result["date"], "Friday")
        self.assertEqual(result["time"], "19:30")
        self.assertEqual(result["party_size"], 2)
        self.assertTrue("booking_id" in result)
        self.assertTrue(result["booking_id"].startswith("BK-"))
        print("\n[TEST] create_booking output:")
        print(json.dumps(result, indent=2))

    def test_modify_booking(self):
        """Test modifying an existing booking with updated details."""
        result = modify_booking(
            booking_id="BK-5421",
            new_date="Sunday",
            new_time="20:30",
            new_party_size=6
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["action"], "modify_booking")
        self.assertEqual(result["booking_id"], "BK-5421")
        self.assertEqual(result["new_date"], "Sunday")
        self.assertEqual(result["new_time"], "20:30")
        self.assertEqual(result["new_party_size"], 6)
        print("\n[TEST] modify_booking output:")
        print(json.dumps(result, indent=2))

    def test_modify_booking_partial(self):
        """Test modifying only one field (e.g. party size only)."""
        result = modify_booking(
            booking_id="BK-5421",
            new_party_size=5
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["action"], "modify_booking")
        self.assertEqual(result["booking_id"], "BK-5421")
        self.assertIsNone(result["new_date"])
        self.assertIsNone(result["new_time"])
        self.assertEqual(result["new_party_size"], 5)

    def test_cancel_booking(self):
        """Test cancelling a booking using booking ID."""
        result = cancel_booking(booking_id="BK-5421")

        self.assertTrue(result["success"])
        self.assertEqual(result["action"], "cancel_booking")
        self.assertEqual(result["booking_id"], "BK-5421")
        self.assertIn("cancelled", result["message"].lower())
        print("\n[TEST] cancel_booking output:")
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    unittest.main()
