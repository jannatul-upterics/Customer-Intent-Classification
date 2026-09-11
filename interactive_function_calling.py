"""
Interactive CLI for Restaurant Function Calling & Dialogue State Tracking.

Allows you to chat live with the assistant in the terminal, observe state updates,
see which Python function gets called, and receive the natural final response.
"""

import sys
import json

# Ensure utf-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from state_manager import BookingState


def main():
    print("=" * 75)
    print("   RESTAURANT FUNCTION CALLING - INTERACTIVE TERMINAL SESSION")
    print("=" * 75)
    print("Commands:")
    print("  - Type any customer message (e.g., 'Do you have a table for 4 tomorrow at 8 PM?')")
    print("  - Type 'state' to view current accumulated conversation state")
    print("  - Type 'reset' to clear conversation state and start fresh")
    print("  - Type 'exit' or 'quit' to end session\n")

    session = BookingState()

    while True:
        try:
            user_input = input("\nCustomer > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nSession ended.")
            break

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit", "q"):
            print("Session ended. Goodbye!")
            break

        if user_input.lower() == "reset":
            session.reset()
            print("[STATE RESET] Conversation state cleared back to defaults.")
            continue

        if user_input.lower() == "state":
            print("[CURRENT STATE]:")
            print(json.dumps(session.to_dict(include_metadata=True), indent=2))
            continue

        # Process turn through the stateful function calling pipeline
        result = session.process_turn(user_input)

        fn_called = result.get("function_called")
        fn_args = result.get("arguments")
        fn_res = result.get("function_result")
        assistant_resp = result.get("final_response")
        curr_state = result.get("state")

        print("-" * 75)
        if fn_called:
            print(f"⚙️  [FUNCTION TRIGGERED]: {fn_called}")
            print(f"📦 [ARGUMENTS]:          {json.dumps(fn_args)}")
            if result.get("summary"):
                print(f"📝 [SUMMARY]:            {result.get('summary')}")
            print(f"📊 [EXECUTION RESULT]:   {json.dumps(fn_res)}")
        else:
            print("💬 [NO FUNCTION CALL]:   Direct conversational reply")
            if result.get("summary"):
                print(f"📝 [SUMMARY]:            {result.get('summary')}")

        print(f"🧠 [UPDATED STATE]:      {json.dumps(curr_state)}")
        print(f"🤖 [ASSISTANT]:\n{assistant_resp}")
        print("-" * 75)


if __name__ == "__main__":
    main()
