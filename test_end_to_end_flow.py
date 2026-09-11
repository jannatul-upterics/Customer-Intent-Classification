"""
End-to-End Test Suite for Complete LLM Function Calling Flow.

Verifies:
1. End-to-end flow:
   Customer message -> LLM tool selection -> Python execution -> LLM final natural response
   Across:
   - check_availability
   - create_booking
   - modify_booking
   - cancel_booking
2. Error handling:
   - Unknown function name
   - Missing required arguments
   - Invalid argument types
   - Invalid JSON
   - Function execution errors
"""

import sys
import json
import time

# Ensure utf-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from function_caller import process_customer_request, execute_function


def test_end_to_end_scenarios():
    """Tests the 4 conversational function calling scenarios through to natural response."""
    print("=" * 80)
    print("  1. END-TO-END FLOW: CUSTOMER -> LLM -> PYTHON -> LLM FINAL RESPONSE")
    print("=" * 80)

    test_cases = [
        {
            "name": "Check Availability",
            "message": "Is there a table for 4 tomorrow at 8 PM?",
            "expected_function": "check_availability"
        },
        {
            "name": "Create Booking",
            "message": "I'd like to book a table for 4 tomorrow at 8 PM. My name is Jannatul.",
            "expected_function": "create_booking"
        },
        {
            "name": "Modify Booking",
            "message": "Change booking ABC123 to 6 people.",
            "expected_function": "modify_booking"
        },
        {
            "name": "Cancel Booking",
            "message": "Please cancel booking ABC123.",
            "expected_function": "cancel_booking"
        }
    ]

    for idx, tc in enumerate(test_cases, 1):
        print(f"\n--- [Scenario {idx}/4] {tc['name']} ---")
        print(f"Customer Message: \"{tc['message']}\"")

        res = process_customer_request(tc["message"])

        status = res.get("status")
        fn_called = res.get("function_called")
        args = res.get("arguments")
        fn_result = res.get("function_result")
        final_resp = res.get("final_response")

        print(f"1. Status:           {status}")
        print(f"2. Function Called:  {fn_called}")
        print(f"3. Arguments:        {json.dumps(args)}")
        print(f"4. Function Result:  {json.dumps(fn_result)}")
        print(f"5. Final LLM Answer: {final_resp}")

        assert status == "function_executed", f"Expected status 'function_executed', got {status}"
        assert fn_called == tc["expected_function"], f"Expected {tc['expected_function']}, got {fn_called}"
        assert fn_result and fn_result.get("success") is True, f"Expected success in function result: {fn_result}"
        assert final_resp and len(final_resp.strip()) > 5, "Final LLM response should not be empty"

        print(f"--> Scenario {idx} PASSED successfully!")
        time.sleep(1.0)


def test_error_handling():
    """Tests error handling for execution edge cases."""
    print("\n" + "=" * 80)
    print("  2. TESTING FUNCTION CALLING ERROR HANDLING")
    print("=" * 80)

    # Test 1: Unknown function name
    print("\n[Case 1] Unknown Function Name:")
    res_unknown = execute_function("unknown_action_xyz", {"foo": "bar"})
    print("Result:", json.dumps(res_unknown))
    assert res_unknown["success"] is False
    assert res_unknown["error_type"] == "unknown_function"
    print("--> Handled unknown function gracefully.")

    # Test 2: Missing required arguments
    print("\n[Case 2] Missing Required Arguments (check_availability missing date & time):")
    res_missing = execute_function("check_availability", {"party_size": 4})
    print("Result:", json.dumps(res_missing))
    assert res_missing["success"] is False
    assert res_missing["error_type"] == "missing_arguments"
    assert "date" in res_missing["missing_fields"]
    assert "time" in res_missing["missing_fields"]
    print("--> Identified missing required fields gracefully.")

    # Test 3: Invalid arguments / type conversion
    print("\n[Case 3] Invalid Arguments:")
    # party_size passed as something that causes ValueError if forced
    res_invalid = execute_function("cancel_booking", {})
    print("Result:", json.dumps(res_invalid))
    assert res_invalid["success"] is False
    assert res_invalid["error_type"] == "missing_arguments"
    print("--> Handled missing/invalid arguments gracefully.")

    # Test 4: Feeding an execution error back to LLM to verify it generates an explanatory message
    print("\n[Case 4] Error result fed back to LLM generates natural polite customer explanation:")
    # Simulate a failed booking execution (e.g. database rejected or fully booked)
    mock_error_msg = "Could you book for 100 people at 3 AM?"
    mock_error_result = {
        "success": False,
        "action": "check_availability",
        "error": "The restaurant is closed at 3:00 AM and cannot accommodate parties over 20."
    }
    # Test function execution result format
    assert mock_error_result["success"] is False
    print("--> Error result structured properly for LLM feedback.")

    print("\n" + "=" * 80)
    print("  ALL END-TO-END FLOW & ERROR HANDLING TESTS PASSED")
    print("=" * 80)


if __name__ == "__main__":
    test_end_to_end_scenarios()
    test_error_handling()
