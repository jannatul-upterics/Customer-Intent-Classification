import unittest
import datetime
import re
from datetime import timedelta

from intent_classifier import (
    resolve_calendar_date,
    build_reference_calendar,
    normalize_booking_data,
    extract_booking_info
)
from state_manager import BookingState


class TestCalendarDateExtraction(unittest.TestCase):
    """
    Test suite verifying calendar date resolution (YYYY-MM-DD) for:
    - Relative weekday expressions (Monday, this Monday, next Monday, Saturday, etc.)
    - Relative days (tomorrow, day after tomorrow)
    - Explicit calendar dates (September 25, 25th September, 09/25/2026)
    - Ambiguous or invalid dates (this weekend, February 31st -> None)
    - Multi-turn date corrections ('Actually, make that Tuesday')
    - Strict YYYY-MM-DD format enforcement (no weekday names returned)
    """

    def setUp(self):
        # Anchor fixed reference date: Thursday, 2026-09-17
        self.fixed_thursday = datetime.date(2026, 9, 17)
        # Anchor fixed reference date: Monday, 2026-09-14
        self.fixed_monday = datetime.date(2026, 9, 14)

    # -------------------------------------------------------------------------
    # 1. Deterministic Weekday Resolution (Anchor: Thursday, 2026-09-17)
    # -------------------------------------------------------------------------
    def test_upcoming_monday_on_thursday(self):
        """'Monday' -> next upcoming Monday (2026-09-21)."""
        res = resolve_calendar_date("Monday", base_date=self.fixed_thursday)
        self.assertEqual(res, "2026-09-21")

    def test_this_monday_on_thursday(self):
        """'this Monday' -> Monday of the current/relevant week (2026-09-14)."""
        res = resolve_calendar_date("this Monday", base_date=self.fixed_thursday)
        self.assertEqual(res, "2026-09-14")

    def test_next_monday_on_thursday(self):
        """'next Monday' -> Monday of the following week (2026-09-21)."""
        res = resolve_calendar_date("next Monday", base_date=self.fixed_thursday)
        self.assertEqual(res, "2026-09-21")

    def test_upcoming_saturday_on_thursday(self):
        """'Saturday' -> next upcoming Saturday (2026-09-19)."""
        res = resolve_calendar_date("Saturday", base_date=self.fixed_thursday)
        self.assertEqual(res, "2026-09-19")

    def test_this_saturday_on_thursday(self):
        """'this Saturday' -> Saturday of the current week (2026-09-19)."""
        res = resolve_calendar_date("this Saturday", base_date=self.fixed_thursday)
        self.assertEqual(res, "2026-09-19")

    def test_next_saturday_on_thursday(self):
        """'next Saturday' -> Saturday of the following week (2026-09-26)."""
        res = resolve_calendar_date("next Saturday", base_date=self.fixed_thursday)
        self.assertEqual(res, "2026-09-26")

    def test_saturday_with_time_expression(self):
        """'Saturday at 8 PM' -> resolves Saturday to 2026-09-19."""
        res = resolve_calendar_date("Saturday at 8 PM", base_date=self.fixed_thursday)
        self.assertEqual(res, "2026-09-19")

    # -------------------------------------------------------------------------
    # 2. Relative Days (tomorrow, day after tomorrow)
    # -------------------------------------------------------------------------
    def test_tomorrow_resolution(self):
        """'tomorrow' -> tomorrow's actual date (2026-09-18)."""
        res = resolve_calendar_date("tomorrow", base_date=self.fixed_thursday)
        self.assertEqual(res, "2026-09-18")

    def test_day_after_tomorrow_resolution(self):
        """'day after tomorrow' -> actual date 2 days ahead (2026-09-19)."""
        res = resolve_calendar_date("day after tomorrow", base_date=self.fixed_thursday)
        self.assertEqual(res, "2026-09-19")

    # -------------------------------------------------------------------------
    # 3. Explicit Calendar Dates
    # -------------------------------------------------------------------------
    def test_explicit_month_day(self):
        """'September 25' -> '2026-09-25'."""
        res = resolve_calendar_date("September 25", base_date=self.fixed_thursday)
        self.assertEqual(res, "2026-09-25")

    def test_explicit_day_month_ordinal(self):
        """'25th September' -> '2026-09-25'."""
        res = resolve_calendar_date("25th September", base_date=self.fixed_thursday)
        self.assertEqual(res, "2026-09-25")

    def test_explicit_numerical_date(self):
        """'09/25/2026' -> '2026-09-25'."""
        res = resolve_calendar_date("09/25/2026", base_date=self.fixed_thursday)
        self.assertEqual(res, "2026-09-25")

    def test_weekday_with_consistent_date(self):
        """'Friday, September 25' -> '2026-09-25'."""
        res = resolve_calendar_date("Friday, September 25", base_date=self.fixed_thursday)
        self.assertEqual(res, "2026-09-25")

    # -------------------------------------------------------------------------
    # 4. Ambiguous & Impossible Dates (Must resolve to None)
    # -------------------------------------------------------------------------
    def test_vague_weekend_expressions(self):
        """'this weekend' and 'next weekend' -> None."""
        self.assertIsNone(resolve_calendar_date("this weekend", base_date=self.fixed_thursday))
        self.assertIsNone(resolve_calendar_date("next weekend", base_date=self.fixed_thursday))

    def test_impossible_calendar_dates(self):
        """'February 31st', 'February 30th' -> None."""
        self.assertIsNone(resolve_calendar_date("February 31st", base_date=self.fixed_thursday))
        self.assertIsNone(resolve_calendar_date("February 30th", base_date=self.fixed_thursday))
        self.assertIsNone(resolve_calendar_date("2026-02-31", base_date=self.fixed_thursday))

    # -------------------------------------------------------------------------
    # 5. Dynamic Runtime Date (Never Hard-Coded)
    # -------------------------------------------------------------------------
    def test_dynamic_runtime_date_default(self):
        """Omitting base_date must use datetime.date.today() dynamically."""
        today = datetime.date.today()
        res_tomorrow = resolve_calendar_date("tomorrow")
        expected_tomorrow = (today + timedelta(days=1)).isoformat()
        self.assertEqual(res_tomorrow, expected_tomorrow)

    def test_weekday_calculation_from_monday(self):
        """Anchor base_date on Monday (2026-09-14)."""
        # Upcoming Friday:
        self.assertEqual(resolve_calendar_date("Friday", base_date=self.fixed_monday), "2026-09-18")
        # this Friday:
        self.assertEqual(resolve_calendar_date("this Friday", base_date=self.fixed_monday), "2026-09-18")
        # next Friday:
        self.assertEqual(resolve_calendar_date("next Friday", base_date=self.fixed_monday), "2026-09-25")

    # -------------------------------------------------------------------------
    # 6. normalize_booking_data Integration
    # -------------------------------------------------------------------------
    def test_normalize_booking_data_date_resolution(self):
        """normalize_booking_data converts raw weekday/date to YYYY-MM-DD."""
        raw = {"intent": "booking", "party_size": 4, "date": "Monday", "time": "20:00"}
        normalized = normalize_booking_data(raw, base_date=self.fixed_thursday)
        self.assertEqual(normalized["date"], "2026-09-21")

        raw_this = {"intent": "booking", "party_size": 4, "date": "this Monday", "time": "20:00"}
        normalized_this = normalize_booking_data(raw_this, base_date=self.fixed_thursday)
        self.assertEqual(normalized_this["date"], "2026-09-14")

        raw_vague = {"intent": "booking", "party_size": 4, "date": "this weekend", "time": "20:00"}
        normalized_vague = normalize_booking_data(raw_vague, base_date=self.fixed_thursday)
        self.assertIsNone(normalized_vague["date"])

    # -------------------------------------------------------------------------
    # 7. Single-Turn Live Extraction
    # -------------------------------------------------------------------------
    def test_live_single_turn_date_extraction(self):
        """Verify live extract_booking_info converts relative expressions to YYYY-MM-DD."""
        res1 = extract_booking_info("Table for 4 this Monday at 7 PM")
        self.assertNotIn("error", res1)
        self.assertRegex(res1["date"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertNotEqual(res1["date"], "Monday")
        self.assertEqual(res1["time"], "19:00")
        self.assertEqual(res1["party_size"], 4)

        res2 = extract_booking_info("Table for 2 on September 25 at 8 PM")
        self.assertNotIn("error", res2)
        self.assertEqual(res2["date"], "2026-09-25")
        self.assertEqual(res2["time"], "20:00")
        self.assertEqual(res2["party_size"], 2)

    # -------------------------------------------------------------------------
    # 8. Multi-Turn Conversation Date Change
    # -------------------------------------------------------------------------
    def test_multi_turn_date_change_flow(self):
        """
        Verify the exact sequence from the user prompt:
        Customer: 'I want a table for 4 people.'
        Customer: 'Monday at 8 PM.'
        State: party_size=4, date=YYYY-MM-DD (upcoming Monday), time=20:00
        Customer: 'Actually, make that Tuesday.'
        State: party_size=4, date=YYYY-MM-DD (Tuesday), time=20:00
        """
        state = BookingState()
        s1 = state.process_message("I want a table for 4 people.")
        self.assertEqual(s1["party_size"], 4)
        self.assertIsNone(s1["date"])
        self.assertIsNone(s1["time"])

        s2 = state.process_message("Monday at 8 PM.")
        self.assertEqual(s2["party_size"], 4)
        self.assertRegex(s2["date"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertNotEqual(s2["date"], "Monday")
        self.assertEqual(s2["time"], "20:00")

        # Capture upcoming Monday
        monday_date = s2["date"]

        s3 = state.process_message("Actually, make that Tuesday.")
        self.assertEqual(s3["party_size"], 4)
        self.assertRegex(s3["date"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertNotEqual(s3["date"], "Tuesday")
        self.assertEqual(s3["time"], "20:00")
        # Tuesday must be exactly 1 day after Monday
        parsed_monday = datetime.date.fromisoformat(monday_date)
        parsed_tuesday = datetime.date.fromisoformat(s3["date"])
        self.assertEqual(parsed_tuesday - parsed_monday, timedelta(days=1))


if __name__ == "__main__":
    unittest.main()
