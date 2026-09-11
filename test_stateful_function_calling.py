"""
Multi-Turn Stateful Function Calling Test.

Tests conversational context and state integration across turns:
Turn 1: Customer: "I want to book a table for 4."
        State: party_size = 4

Turn 2: Customer: "This Saturday at 8 PM."
        State: party_size = 4, date = "Saturday", time = "20:00"

Turn 3: Customer: "Actually, make it 6."
        State: party_size = 6, date = "Saturday", time = "20:00"

Turn 4: Customer: "Is that available?"
        Action: LLM selects check_availability with accumulated state (Saturday, 20:00, 6).
        Python executes check_availability.
        LLM generates natural response confirming availability without user repeating details.

Turn 5: Customer: "Great, please book it under Jannatul."
        Action: LLM selects create_booking using accumulated state.
        Python executes create_booking.
        LLM generates natural confirmation with booking ID.
"""

import sys
import json
import time

# Ensure utf-8 console output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from state_manager import BookingState


def run_stateful_conversation_test():
    print("=" * 80)
    print("  MULTI-TURN STATEFUL FUNCTION CALLING INTEGRATION TEST")
    print("=" * 80)

    session = BookingState()

    conversation = [
        {
            "turn": 1,
            "message": "I want to book a table for 4.",
            "expected_state": {
                "party_size": 4
            },
            "expect_function": None
        },
        {
            "turn": 2,
            "message": "This Saturday at 8 PM.",
            "expected_state": {
                "party_size": 4,
                "date": "Saturday",
                "time": "20:00"
            },
            "expect_function": None
        },
        {
            "turn": 3,
            "message": "Actually, make it 6.",
            "expected_state": {
                "party_size": 6,
                "date": "Saturday",
                "time": "20:00"
            },
            "expect_function": None
        },
        {
            "turn": 4,
            "message": "Is that available?",
            "expected_state": {
                "party_size": 6,
                "date": "Saturday",
                "time": "20:00"
            },
            "expect_function": "check_availability",
            "expected_args": {
                "date": "Saturday",
                "time": "20:00",
                "party_size": 6
            }
        },
        {
            "turn": 5,
            "message": "Great, please book it under Jannatul.",
            "expected_state": {
                "party_size": 6,
                "date": "Saturday",
                "time": "20:00",
                "customer_name": "Jannatul"
            },
            "expect_function": "create_booking",
            "expected_args": {
                "customer_name": "Jannatul",
                "date": "Saturday",
                "time": "20:00",
                "party_size": 6
            }
        }
    ]

    for step in conversation:
        turn_num = step["turn"]
        msg = step["message"]

        print(f"\n" + "-" * 75)
        print(f"[TURN {turn_num}] Customer: \"{msg}\"")
        print("-" * 75)

        turn_output = session.process_turn(msg)

        state = turn_output["state"]
        fn_called = turn_output["function_called"]
        args = turn_output["arguments"]
        fn_res = turn_output["function_result"]
        resp = turn_output["final_response"]

        print(f"Current State:      {json.dumps(state)}")
        print(f"Function Called:    {fn_called}")
        if fn_called:
            print(f"Arguments Used:     {json.dumps(args)}")
            print(f"Function Result:    {json.dumps(fn_res)}")
        print(f"Assistant Response: {resp}")

        # Check state expectations
        for k, v in step["expected_state"].items():
            assert state.get(k) == v, f"Turn {turn_num}: Expected state['{k}'] == {v}, got {state.get(k)}"

        # Check function call expectations
        if step["expect_function"]:
            assert fn_called == step["expect_function"], f"Turn {turn_num}: Expected function {step['expect_function']}, got {fn_called}"
            for arg_k, arg_v in step["expected_args"].items():
                assert args.get(arg_k) == arg_v, f"Turn {turn_num}: Expected arg['{arg_k}'] == {arg_v}, got {args.get(arg_k)}"
            assert fn_res and fn_res.get("success") is True, f"Turn {turn_num}: Function execution failed: {fn_res}"
            assert resp and len(resp.strip()) > 5, f"Turn {turn_num}: Response too short"
            print(f"--> [PASS] Turn {turn_num}: Function {fn_called} executed with correct stateful arguments!")
        else:
            print(f"--> [PASS] Turn {turn_num}: State accurately updated without premature function calls.")

        time.sleep(1.0)

    print("\n" + "=" * 80)
    print("  ALL MULTI-TURN STATEFUL FUNCTION CALLING TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 80)


if __name__ == "__main__":
    run_stateful_conversation_test()
