"""
Prototype Demonstration Runner.

Runs each of the four restaurant functions with example inputs
and displays their structured outputs without requiring an LLM connection.
"""

import json
import sys

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from actions import (
    check_availability,
    create_booking,
    modify_booking,
    cancel_booking
)


def run_demonstration():
    print("=" * 70)
    print("   RESTAURANT FUNCTION CALLING PROTOTYPE (STANDALONE DEMO)")
    print("=" * 70)

    # 1. Check Availability
    print("\n--- 1. Check Availability ---")
    print("Input: date='2026-09-12', time='20:00', number_of_guests=4")
    res1 = check_availability(date="2026-09-12", time="20:00", number_of_guests=4)
    print("Output:")
    print(json.dumps(res1, indent=2))

    # 2. Create Booking
    print("\n--- 2. Create Booking ---")
    print("Input: customer_name='Jannatul', date='2026-09-12', time='20:00', number_of_guests=4")
    res2 = create_booking(customer_name="Jannatul", date="2026-09-12", time="20:00", number_of_guests=4)
    print("Output:")
    print(json.dumps(res2, indent=2))

    booking_id = res2.get("booking_id", "RES-1234")

    # 3. Modify Booking
    print(f"\n--- 3. Modify Booking ---")
    print(f"Input: booking_id='{booking_id}', new_number_of_guests=6, new_time='20:30'")
    res3 = modify_booking(booking_id=booking_id, new_number_of_guests=6, new_time="20:30")
    print("Output:")
    print(json.dumps(res3, indent=2))

    # 4. Cancel Booking
    print(f"\n--- 4. Cancel Booking ---")
    print(f"Input: booking_id='{booking_id}'")
    res4 = cancel_booking(booking_id=booking_id)
    print("Output:")
    print(json.dumps(res4, indent=2))

    # 5. Error Handling Demonstration
    print("\n--- 5. Error Handling Sample ---")
    print("Input: create_booking with missing customer_name and negative guests")
    err_res = create_booking(customer_name="", date="2026-09-12", time="20:00", number_of_guests=-2)
    print("Output:")
    print(json.dumps(err_res, indent=2))

    print("\n" + "=" * 70)
    print("   DEMONSTRATION COMPLETE - ALL 4 ACTIONS EXECUTED")
    print("=" * 70)


if __name__ == "__main__":
    run_demonstration()
