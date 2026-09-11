"""
Evaluation Runner for 10 Realistic Restaurant Booking Function Calling Conversations.

Covers the 10 required test scenarios:
1. Customer asks about availability
2. Customer wants to create a new booking
3. Customer modifies the number of guests
4. Customer modifies the date
5. Customer modifies the time
6. Customer cancels an existing booking
7. Customer provides booking information over multiple messages
8. Customer changes previously provided information and then asks for availability
9. Customer uses informal/conversational wording
10. Customer changes their intention during the conversation
"""

import os
import sys
import json
import time

# Ensure utf-8 console output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from state_manager import BookingState


TEST_CONVERSATIONS = [
    {
        "id": "TC-001",
        "name": "Customer asks about availability",
        "type": "single_turn",
        "turns": [
            "Can you check if you have an open table for 5 people this Friday at 7:30 PM?"
        ],
        "target_turn": -1,
        "expected_function": "check_availability",
        "expected_arguments": {
            "date": "Friday",
            "time": "19:30",
            "party_size": 5
        }
    },
    {
        "id": "TC-002",
        "name": "Customer wants to create a new booking",
        "type": "single_turn",
        "turns": [
            "I'd like to book a table for 2 guests under Sarah Jenkins for tomorrow at 8:00 PM, please."
        ],
        "target_turn": -1,
        "expected_function": "create_booking",
        "expected_arguments": {
            "customer_name": "Sarah Jenkins",
            "date": "tomorrow",
            "time": "20:00",
            "party_size": 2
        }
    },
    {
        "id": "TC-003",
        "name": "Customer modifies the number of guests",
        "type": "single_turn",
        "turns": [
            "Hello, could we change the party size for reservation BK-2041 to 6 people?"
        ],
        "target_turn": -1,
        "expected_function": "modify_booking",
        "expected_arguments": {
            "booking_id": "BK-2041",
            "new_party_size": 6
        }
    },
    {
        "id": "TC-004",
        "name": "Customer modifies the date",
        "type": "single_turn",
        "turns": [
            "Hi, I have a reservation with ID ABC789. Can we move it to Sunday instead?"
        ],
        "target_turn": -1,
        "expected_function": "modify_booking",
        "expected_arguments": {
            "booking_id": "ABC789",
            "new_date": "Sunday"
        }
    },
    {
        "id": "TC-005",
        "name": "Customer modifies the time",
        "type": "single_turn",
        "turns": [
            "Regarding booking BK-4092, could we push our reservation time back to 9:00 PM?"
        ],
        "target_turn": -1,
        "expected_function": "modify_booking",
        "expected_arguments": {
            "booking_id": "BK-4092",
            "new_time": "21:00"
        }
    },
    {
        "id": "TC-006",
        "name": "Customer cancels an existing booking",
        "type": "single_turn",
        "turns": [
            "Hi, we unfortunately won't be able to make it tonight. Please cancel booking BK-8812."
        ],
        "target_turn": -1,
        "expected_function": "cancel_booking",
        "expected_arguments": {
            "booking_id": "BK-8812"
        }
    },
    {
        "id": "TC-007",
        "name": "Customer provides booking information over multiple messages",
        "type": "multi_turn",
        "turns": [
            "Hi, I'd like to reserve a table for an anniversary dinner.",
            "There will be 2 of us this Saturday at 7 PM.",
            "Please confirm the reservation under David Miller."
        ],
        "target_turn": -1,
        "expected_function": "create_booking",
        "expected_arguments": {
            "customer_name": "David Miller",
            "date": "Saturday",
            "time": "19:00",
            "party_size": 2
        }
    },
    {
        "id": "TC-008",
        "name": "Customer changes previously provided information and then asks for availability",
        "type": "multi_turn",
        "turns": [
            "Do you have space for 4 people on Friday at 8 PM?",
            "Actually, two more friends are joining us, make it 6 people instead.",
            "Is a table available for that?"
        ],
        "target_turn": -1,
        "expected_function": "check_availability",
        "expected_arguments": {
            "date": "Friday",
            "time": "20:00",
            "party_size": 6
        }
    },
    {
        "id": "TC-009",
        "name": "Customer uses informal/conversational wording",
        "type": "single_turn",
        "turns": [
            "Hey! Me and 3 buddies wanna grab dinner tomorrow around 8-ish in the evening. Got room for us?"
        ],
        "target_turn": -1,
        "expected_function": "check_availability",
        "expected_arguments": {
            "date": "tomorrow",
            "time": "20:00",
            "party_size": 4
        }
    },
    {
        "id": "TC-010",
        "name": "Customer changes their intention during the conversation",
        "type": "multi_turn",
        "turns": [
            "Hi, I have reservation BK-5521 and I wanted to change it to 5 people.",
            "Actually, never mind changing it, our plans fell through completely. Please cancel the booking."
        ],
        "target_turn": -1,
        "expected_function": "cancel_booking",
        "expected_arguments": {
            "booking_id": "BK-5521"
        }
    }
]


def compare_arguments(actual: dict, expected: dict) -> bool:
    """Compares actual extracted arguments with expected arguments."""
    if not isinstance(actual, dict) or not isinstance(expected, dict):
        return False

    for k, exp_val in expected.items():
        act_val = actual.get(k)
        if act_val is None:
            return False

        if isinstance(exp_val, int):
            try:
                if int(act_val) != exp_val:
                    return False
            except (ValueError, TypeError):
                return False
        elif isinstance(exp_val, str):
            if str(act_val).strip().lower() != exp_val.strip().lower():
                return False
        elif act_val != exp_val:
            return False

    return True


def run_evaluation():
    print("=" * 80)
    print("  RUNNING 10 REALISTIC RESTAURANT BOOKING FUNCTION CALLING CONVERSATIONS")
    print("=" * 80)

    results = []
    passed_count = 0

    for idx, tc in enumerate(TEST_CONVERSATIONS, 1):
        tc_id = tc["id"]
        name = tc["name"]
        turns = tc["turns"]
        expected_fn = tc["expected_function"]
        expected_args = tc["expected_arguments"]

        print(f"\n[{idx}/10] {tc_id}: {name}")
        print("-" * 75)

        session = BookingState()
        turn_records = []
        target_turn_result = None

        for t_idx, msg in enumerate(turns, 1):
            print(f"Turn {t_idx} Customer: \"{msg}\"")
            turn_res = session.process_turn(msg)
            turn_records.append({
                "turn": t_idx,
                "message": msg,
                "state": turn_res.get("state"),
                "function_called": turn_res.get("function_called"),
                "arguments": turn_res.get("arguments"),
                "response": turn_res.get("final_response")
            })
            if t_idx == len(turns):
                target_turn_result = turn_res
            time.sleep(1.0)

        actual_fn = target_turn_result.get("function_called")
        actual_args = target_turn_result.get("arguments") or {}

        fn_match = (actual_fn == expected_fn)
        args_match = compare_arguments(actual_args, expected_args)
        is_pass = fn_match and args_match

        status_str = "PASS" if is_pass else "FAIL"
        if is_pass:
            passed_count += 1

        summary_text = target_turn_result.get("summary", "")
        print(f"\nEvaluation for {tc_id}:")
        print(f"  Expected Function:  {expected_fn}")
        print(f"  Expected Arguments: {json.dumps(expected_args)}")
        print(f"  Actual Function:    {actual_fn}")
        print(f"  Actual Arguments:   {json.dumps(actual_args)}")
        if summary_text:
            print(f"  Summary:            {summary_text}")
        print(f"  Status:             [{status_str}]")

        record = {
            "id": tc_id,
            "name": name,
            "turns": turns,
            "expected_function": expected_fn,
            "expected_arguments": expected_args,
            "actual_function": actual_fn,
            "actual_arguments": actual_args,
            "summary": summary_text,
            "status": status_str,
            "final_response": target_turn_result.get("final_response")
        }
        results.append(record)

    summary = {
        "total_test_cases": len(TEST_CONVERSATIONS),
        "passed": passed_count,
        "failed": len(TEST_CONVERSATIONS) - passed_count,
        "accuracy_pct": round(passed_count / len(TEST_CONVERSATIONS) * 100, 1),
        "test_cases": results
    }

    with open("function_calling_test_results.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 80)
    print(f"  EVALUATION COMPLETE: {passed_count}/{len(TEST_CONVERSATIONS)} Passed ({summary['accuracy_pct']}%)")
    print("  Results saved to function_calling_test_results.json")
    print("=" * 80)


if __name__ == "__main__":
    run_evaluation()
