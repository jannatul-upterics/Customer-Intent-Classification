import json
import time
from state_manager import BookingState
from test_multi_turn import compare_state

def run_eval():
    with open("multi_turn_test_dataset.json", "r", encoding="utf-8") as f:
        conversations = json.load(f)[:10]

    all_results = []
    total_turns = 0
    passed_turns = 0
    failed_turns = 0

    print("Starting evaluation of 10 conversations...\n")

    for c_idx, conv in enumerate(conversations, 1):
        conv_id = conv["conversation_id"]
        title = conv.get("title", "")
        focus = conv.get("primary_focus", "")
        turns = conv["turns"]

        print(f"Running {conv_id}: {title}...")
        session = BookingState()
        conv_record = {
            "conversation_id": conv_id,
            "title": title,
            "primary_focus": focus,
            "turns": []
        }

        for turn in turns:
            total_turns += 1
            t_id = turn["turn_id"]
            msg = turn["customer_message"]
            expected = turn["expected_state"]

            # Process through live BookingState
            actual = session.process_message(msg)

            is_match, diffs = compare_state(actual, expected)
            status = "PASS" if is_match else "FAIL"
            if is_match:
                passed_turns += 1
            else:
                failed_turns += 1

            turn_record = {
                "turn_id": t_id,
                "customer_message": msg,
                "actual_state": actual,
                "expected_state": expected,
                "status": status,
                "diffs": diffs
            }
            conv_record["turns"].append(turn_record)
            time.sleep(1.0)

        all_results.append(conv_record)

    summary = {
        "total_conversations": len(conversations),
        "total_turns": total_turns,
        "correct_updates": passed_turns,
        "incorrect_updates": failed_turns,
        "accuracy_pct": round((passed_turns / total_turns * 100), 2) if total_turns > 0 else 0,
        "conversations": all_results
    }

    with open("eval_run_10_convs.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("\nEvaluation Complete!")
    print(f"Total Turns: {total_turns}, Passed: {passed_turns}, Failed: {failed_turns}, Accuracy: {summary['accuracy_pct']}%")

if __name__ == "__main__":
    run_eval()
