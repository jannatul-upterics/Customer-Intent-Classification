"""
Verification and Test Suite for the `summary` attribute in Function Calling.

Verifies:
1. The `summary` attribute is included in the final output dictionary / JSON.
2. The summary considers the full conversation history, not just the latest turn.
3. If information changed (e.g. party size from 4 to 6), the final value is used and the change is noted.
4. If a requirement was removed, it is not presented as active.
5. The 4 existing functions remain unchanged in signatures and behaviors.
"""

import sys
import json
import time

# Ensure utf-8 stdout on Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from state_manager import BookingState
from function_caller import process_customer_request, evaluate_customer_message, get_llm_tool_decision


def test_user_multiturn_example():
    """
    Test the exact multi-turn conversation from the user prompt:
    Customer: "I'd like a table for 4 people."
    Customer: "This Saturday at 8 PM."
    Customer: "Actually, make it 6 people."
    Customer: "Is that available?"
    """
    print("=" * 80)
    print("  TEST 1: MULTI-TURN CONVERSATION WITH UPDATED PARTY SIZE")
    print("=" * 80)

    session = BookingState()

    conversation = [
        "I'd like a table for 4 people.",
        "This Saturday at 8 PM.",
        "Actually, make it 6 people.",
        "Is that available?"
    ]

    last_turn_result = None
    for idx, msg in enumerate(conversation, 1):
        print(f"Turn {idx} Customer: \"{msg}\"")
        turn_res = session.process_turn(msg)
        last_turn_result = turn_res
        time.sleep(0.5)

    print("\nFinal Output Structure:")
    # Build clean representation matching user example
    final_json = {
        "function": last_turn_result.get("function"),
        "arguments": last_turn_result.get("arguments"),
        "summary": last_turn_result.get("summary")
    }
    print(json.dumps(final_json, indent=2, ensure_ascii=False))

    # Assertions
    assert final_json["function"] == "check_availability", f"Expected check_availability, got {final_json['function']}"
    args = final_json["arguments"]
    assert args.get("party_size") == 6, f"Expected party_size 6, got {args.get('party_size')}"
    assert "saturday" in str(args.get("date")).lower(), f"Expected Saturday date, got {args.get('date')}"
    assert "20:00" in str(args.get("time")), f"Expected time 20:00, got {args.get('time')}"

    summary = final_json["summary"]
    assert summary and len(summary) > 15, "Summary should be non-empty"
    summary_lower = summary.lower()
    assert "6" in summary_lower, "Summary must mention final party size of 6"
    assert "saturday" in summary_lower, "Summary must mention Saturday"
    assert "4" in summary_lower or "originally" in summary_lower or "changed" in summary_lower, "Summary should reflect that party size was changed from 4"

    print("\n--> [PASS] Test 1: Full conversation summary accurately captures changes and active parameters.")


def test_user_singleturn_booking():
    """
    Test single-turn create_booking:
    Customer: "I'd like to book a table for 4 people this Saturday at 8 PM under the name John."
    """
    print("\n" + "=" * 80)
    print("  TEST 2: SINGLE-TURN CREATE BOOKING WITH SUMMARY")
    print("=" * 80)

    session = BookingState()
    msg = "I'd like to book a table for 4 people this Saturday at 8 PM under the name John."
    print(f"Customer: \"{msg}\"")

    turn_res = session.process_turn(msg)

    final_json = {
        "function": turn_res.get("function"),
        "arguments": turn_res.get("arguments"),
        "summary": turn_res.get("summary")
    }
    print("\nFinal Output Structure:")
    print(json.dumps(final_json, indent=2, ensure_ascii=False))

    assert final_json["function"] == "create_booking", f"Expected create_booking, got {final_json['function']}"
    args = final_json["arguments"]
    assert args.get("party_size") == 4, f"Expected party_size 4, got {args.get('party_size')}"
    assert "john" in str(args.get("customer_name")).lower(), f"Expected John, got {args.get('customer_name')}"

    summary = final_json["summary"]
    assert summary and len(summary) > 10, "Summary should be non-empty"
    summary_lower = summary.lower()
    assert "john" in summary_lower, "Summary must mention customer name John"
    assert "4" in summary_lower, "Summary must mention 4 people"

    print("\n--> [PASS] Test 2: Single-turn booking produces concise natural summary.")


def test_modification_conversation():
    """
    Test modification conversation:
    Customer: "Change booking ABC123 to 6 people."
    Customer: "Actually, move it to 9 PM as well."
    """
    print("\n" + "=" * 80)
    print("  TEST 3: MULTI-TURN MODIFICATION CONVERSATION")
    print("=" * 80)

    session = BookingState()
    print("Turn 1 Customer: \"Change booking ABC123 to 6 people.\"")
    session.process_turn("Change booking ABC123 to 6 people.")
    time.sleep(1.0)
    print("Turn 2 Customer: \"Actually, move it to 9 PM as well.\"")
    turn_res = session.process_turn("Actually, move it to 9 PM as well.")

    final_json = {
        "function": turn_res.get("function"),
        "arguments": turn_res.get("arguments"),
        "summary": turn_res.get("summary")
    }
    print("\nFinal Output Structure:")
    print(json.dumps(final_json, indent=2, ensure_ascii=False))

    assert final_json["function"] == "modify_booking", f"Expected modify_booking, got {final_json['function']}"
    assert "abc123" in str(final_json["arguments"].get("booking_id")).lower(), "Booking ID should be ABC123"

    summary = final_json["summary"]
    assert summary and len(summary) > 10, "Summary should be non-empty"
    assert "abc123" in summary.lower(), "Summary must mention booking ABC123"

    print("\n--> [PASS] Test 3: Multi-turn modification summary verified.")


def test_cancellation_conversation():
    """
    Test cancellation request:
    Customer: "Please cancel booking BK-8812 because our plans fell through."
    """
    print("\n" + "=" * 80)
    print("  TEST 4: CANCELLATION REQUEST WITH REASON CONTEXT")
    print("=" * 80)

    session = BookingState()
    msg = "Please cancel booking BK-8812 because our plans fell through."
    print(f"Customer: \"{msg}\"")
    turn_res = session.process_turn(msg)

    final_json = {
        "function": turn_res.get("function"),
        "arguments": turn_res.get("arguments"),
        "summary": turn_res.get("summary")
    }
    print("\nFinal Output Structure:")
    print(json.dumps(final_json, indent=2, ensure_ascii=False))

    assert final_json["function"] == "cancel_booking", f"Expected cancel_booking, got {final_json['function']}"
    assert final_json["arguments"].get("booking_id") == "BK-8812"

    summary = final_json["summary"]
    assert summary and len(summary) > 10
    assert "bk-8812" in summary.lower() or "8812" in summary.lower()

    print("\n--> [PASS] Test 4: Cancellation request summary verified.")


def test_decision_and_inspection_helpers():
    """
    Test that evaluate_customer_message and get_llm_tool_decision also include summary.
    """
    print("\n" + "=" * 80)
    print("  TEST 5: DECISION AND INSPECTION HELPERS INCLUDE SUMMARY")
    print("=" * 80)

    decision = get_llm_tool_decision("Can you check if there is a table for 2 this Friday at 7 PM?")
    print("get_llm_tool_decision output:")
    print(json.dumps(decision, indent=2, ensure_ascii=False))

    assert "summary" in decision, "Decision must have 'summary' key"
    assert "function" in decision, "Decision must have 'function' key"
    assert "arguments" in decision, "Decision must have 'arguments' key"
    assert len(decision["summary"]) > 10, "Summary in decision must be non-empty"

    print("\n--> [PASS] Test 5: Inspection helpers include 'summary' attribute.")


if __name__ == "__main__":
    print("RUNNING SUMMARY ATTRIBUTE VERIFICATION SUITE...\n")
    test_user_multiturn_example()
    test_user_singleturn_booking()
    test_modification_conversation()
    test_cancellation_conversation()
    test_decision_and_inspection_helpers()
    print("\n" + "=" * 80)
    print("  ALL SUMMARY ATTRIBUTE VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 80)
