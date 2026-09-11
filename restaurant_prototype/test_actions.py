"""
Unit Tests for Restaurant Prototype Actions.

Verifies:
1. check_availability: Valid call and negative/zero guest handling
2. create_booking: Valid call, missing customer name, generated booking ID
3. modify_booking: Partial modification, full modification, no modification fields error
4. cancel_booking: Valid cancellation, missing booking ID error
"""

import unittest
from actions import (
    check_availability,
    create_booking,
    modify_booking,
    cancel_booking
)


class TestRestaurantActions(unittest.TestCase):

    def test_check_availability_success(self):
        res = check_availability(date="2026-09-12", time="20:00", number_of_guests=4)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["action"], "check_availability")
        self.assertTrue(res["available"])
        self.assertEqual(res["number_of_guests"], 4)
        self.assertEqual(res["date"], "2026-09-12")
        self.assertEqual(res["time"], "20:00")

    def test_check_availability_invalid_guests(self):
        res = check_availability(date="2026-09-12", time="20:00", number_of_guests=-1)
        self.assertEqual(res["status"], "error")
        self.assertIn("positive integer", res["error"])

    def test_create_booking_success(self):
        res = create_booking(customer_name="Alice Smith", date="Saturday", time="19:30", number_of_guests=2)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["action"], "create_booking")
        self.assertEqual(res["customer_name"], "Alice Smith")
        self.assertEqual(res["number_of_guests"], 2)
        self.assertTrue("booking_id" in res)
        self.assertTrue(res["booking_id"].startswith("RES-"))

    def test_create_booking_missing_name(self):
        res = create_booking(customer_name="", date="Saturday", time="19:30", number_of_guests=2)
        self.assertEqual(res["status"], "error")
        self.assertIn("customer_name is required", res["error"])

    def test_modify_booking_success(self):
        res = modify_booking(booking_id="RES-1234", new_number_of_guests=6, new_time="21:00")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["action"], "modify_booking")
        self.assertEqual(res["booking_id"], "RES-1234")
        self.assertEqual(res["updated_fields"]["number_of_guests"], 6)
        self.assertEqual(res["updated_fields"]["time"], "21:00")

    def test_modify_booking_no_fields(self):
        res = modify_booking(booking_id="RES-1234")
        self.assertEqual(res["status"], "error")
        self.assertIn("At least one field", res["error"])

    def test_cancel_booking_success(self):
        res = cancel_booking(booking_id="RES-1234")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["action"], "cancel_booking")
        self.assertEqual(res["booking_id"], "RES-1234")
        self.assertIn("cancelled", res["message"].lower())

    def test_cancel_booking_missing_id(self):
        res = cancel_booking(booking_id="")
        self.assertEqual(res["status"], "error")
        self.assertIn("booking_id is required", res["error"])


if __name__ == "__main__":
    unittest.main()
