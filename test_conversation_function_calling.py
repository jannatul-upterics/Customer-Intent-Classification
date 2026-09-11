"""
Tests for Connecting Customer Conversations to the LLM Function Calling System.

Covers:
1. Availability check: "Is there a table available for 4 people tomorrow at 8 PM?"
2. New booking creation: "I'd like to book a table for 4 people tomorrow at 8 PM. My name is Jannatul."
3. Modification: "Change booking ABC123 to 6 people."
4. Cancellation: "Please cancel booking ABC123."
5. Unnecessary call prevention: "What are your restaurant opening hours on Sunday?"
6. Missing required information detection without guessing: "Please cancel my table reservation."
"""

import sys
import json
import time

# Ensure utf-8 stdout on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from function_caller import evaluate_customer_message



def run_tests():
    test_cases = [
        {
            "category": "1. Check Availability",
            "message": "Is there a table available for 4 people tomorrow at 8 PM?",
            "expected_function": "check_availability",
            "expected_arguments": {
                "date": "tomorrow",
                "time": "20:00",
                "party_size": 4
            }
        },
        {
            "category": "2. Create Booking",
            "message": "I'd like to book a table for 4 people tomorrow at 8 PM. My name is Jannatul.",
            "expected_function": "create_booking",
            "expected_arguments": {
                "customer_name": "Jannatul",
                "date": "tomorrow",
                "time": "20:00",
                "party_size": 4
            }
        },
        {
            "category": "3. Modify Booking",
            "message": "Change booking ABC123 to 6 people.",
            "expected_function": "modify_booking",
            "expected_arguments": {
                "booking_id": "ABC123",
                "new_party_size": 6
            }
        },
        {
            "category": "4. Cancel Booking",
            "message": "Please cancel booking ABC123.",
            "expected_function": "cancel_booking",
            "expected_arguments": {
                "booking_id": "ABC123"
            }
        },
        {
            "category": "5. Prevent Unnecessary Function Call (General Inquiry)",
            "message": "What are your opening hours on Sundays?",
            "expected_function": None,
            "expected_arguments": {}
        },
        {
            "category": "6. Missing Required Information (No Booking ID Given)",
            "message": "Please cancel my table reservation.",
            "expected_function": "cancel_booking_or_direct_ask",
            "expected_arguments": None
        }
    ]

    print("=" * 75)
    print("  RUNNING LLM FUNCTION CALLING EVALUATION ON CUSTOMER CONVERSATIONS")
    print("=" * 75)

    passed = 0
    total = len(test_cases)

    for idx, tc in enumerate(test_cases, 1):
        print(f"\n[{idx}/{total}] Category: {tc['category']}")
        print(f"Customer Input: \"{tc['message']}\"")

        res = evaluate_customer_message(tc["message"])

        status = res.get("status")
        func = res.get("function")
        args = res.get("arguments", {})

        print(f"  Decision Status: {status}")
        print(f"  Decided Function: {func}")
        print(f"  Extracted Arguments: {json.dumps(args)}")

        is_correct = False

        if tc["expected_function"] is None:
            # Should NOT call a function
            is_correct = (status == "no_function_call" and func is None)
            print(f"  Response Message: {res.get('response_message', '').strip()[:100]}...")
        elif tc["expected_function"] == "cancel_booking_or_direct_ask":
            # Either LLM asks directly for booking ID, or flags missing_information
            is_correct = (status in ("missing_information", "no_function_call"))
            if status == "missing_information":
                print(f"  Identified Missing Fields: {res.get('missing_fields')}")
            else:
                print(f"  Direct Response Asking for Details: {res.get('response_message', '').strip()[:100]}...")
        else:
            # Check function name and arguments match
            func_match = (func == tc["expected_function"])
            exp_args = tc["expected_arguments"]

            args_match = True
            for k, v in exp_args.items():
                if args.get(k) != v:
                    args_match = False
                    break

            is_correct = func_match and args_match

        if is_correct:
            passed += 1
            print("  Result: [PASS]")
        else:
            print("  Result: [FAIL]")
            print(f"    Expected Function: {tc['expected_function']}")
            print(f"    Expected Arguments: {tc['expected_arguments']}")

        time.sleep(1.0)

    print("\n" + "=" * 75)
    print(f"  EVALUATION SUMMARY: {passed}/{total} Passed ({(passed/total)*100:.1f}%)")
    print("=" * 75)


if __name__ == "__main__":
    run_tests()
