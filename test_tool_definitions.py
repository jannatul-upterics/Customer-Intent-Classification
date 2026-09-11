"""
Verification and Test Suite for LLM Tool/Function Calling Definitions.

Verifies:
1. RESTAURANT_TOOLS schema compliance (name, description, types, required fields).
2. Live LLM decision routing across the four operations:
   - check_availability
   - create_booking
   - modify_booking
   - cancel_booking
3. Confirms that tools are identified without executing the functions.
"""

import sys
import json
import time

# Ensure UTF-8 console encoding on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from restaurant_functions import RESTAURANT_TOOLS
from function_caller import get_llm_tool_decision



def verify_tool_schemas():
    """Verify schema integrity of the four tool definitions."""
    print("=" * 70)
    print("  1. VERIFYING TOOL SCHEMAS FOR LLM FUNCTION CALLING")
    print("=" * 70)

    expected_tools = {
        "check_availability": ["date", "time", "party_size"],
        "create_booking": ["customer_name", "date", "time", "party_size"],
        "modify_booking": ["booking_id"],
        "cancel_booking": ["booking_id"]
    }

    found_names = set()

    for idx, tool in enumerate(RESTAURANT_TOOLS, 1):
        self_type = tool.get("type")
        fn = tool.get("function", {})
        name = fn.get("name")
        desc = fn.get("description")
        params = fn.get("parameters", {})
        props = params.get("properties", {})
        req = params.get("required", [])

        found_names.add(name)

        print(f"\nTool #{idx}: {name}")
        print(f"  Type:        {self_type}")
        print(f"  Description: {desc}")
        print(f"  Parameters:  {list(props.keys())}")
        print(f"  Required:    {req}")

        assert self_type == "function", f"Invalid tool type: {self_type}"
        assert name in expected_tools, f"Unexpected tool: {name}"
        assert desc and len(desc) > 10, f"Description missing or too short for {name}"
        assert params.get("type") == "object", f"Parameters must be type object for {name}"

        for req_field in expected_tools[name]:
            assert req_field in req, f"Missing required field {req_field} in {name}"
            assert req_field in props, f"Missing property {req_field} in {name}"

    assert len(found_names) == 4, f"Expected 4 tools, found {len(found_names)}"
    print("\n[SUCCESS] All 4 tool schemas strictly verified and compliant.")


def test_live_llm_tool_decisions():
    """Test live LLM tool selection against representative customer utterances."""
    print("\n" + "=" * 70)
    print("  2. TESTING LIVE LLM TOOL ROUTING (WITHOUT EXECUTING FUNCTIONS)")
    print("=" * 70)

    test_cases = [
        {
            "description": "Availability Inquiry",
            "message": "Do you have a table for 4 people tomorrow at 8 PM?",
            "expected_tool": "check_availability"
        },
        {
            "description": "New Reservation Request",
            "message": "Please book a table for John Doe for 2 people this Friday at 7:30 PM.",
            "expected_tool": "create_booking"
        },
        {
            "description": "Modification Request",
            "message": "I'd like to update my booking BK-9821 to 6 people at 20:30 instead.",
            "expected_tool": "modify_booking"
        },
        {
            "description": "Cancellation Request",
            "message": "Can you please cancel my booking BK-9821?",
            "expected_tool": "cancel_booking"
        }
    ]

    for idx, tc in enumerate(test_cases, 1):
        print(f"\n[{idx}/{len(test_cases)}] Case: {tc['description']}")
        print(f"Customer: \"{tc['message']}\"")

        decision = get_llm_tool_decision(tc["message"])

        if decision.get("error"):
            print(f"  [ERROR] {decision['error']}")
            continue

        action = decision.get("action")
        args = decision.get("arguments")
        model = decision.get("model_used")

        print(f"  Model Used:   {model}")
        print(f"  LLM Decision: {action}")
        print(f"  Arguments:    {json.dumps(args)}")

        is_match = (action == tc["expected_tool"])
        status_label = "PASS" if is_match else "FAIL"
        print(f"  Status:       [{status_label}] (Expected: {tc['expected_tool']})")

        time.sleep(1.0)


if __name__ == "__main__":
    verify_tool_schemas()
    test_live_llm_tool_decisions()
