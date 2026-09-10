"""
Evaluation runner for Multi-Turn Restaurant Booking Conversations.

Loads multi-turn test conversations from `multi_turn_test_dataset.json`,
runs each conversation step-by-step through BookingState, compares the actual state
against the expected state at each turn, and outputs a formatted evaluation report.
"""

import os
import sys
import json
import time
from state_manager import BookingState

DATASET_FILE = "multi_turn_test_dataset.json"
RESULTS_FILE = "multi_turn_test_results.json"


def compare_state(actual: dict, expected: dict) -> tuple:
    """
    Compares actual state against expected state across all 5 fields.
    Returns (is_match: bool, differences: list).
    """
    diffs = []
    if not isinstance(actual, dict):
        return False, ["Actual state is not a dict"]

    # 1. intent
    act_intent = str(actual.get("intent") or "").strip().lower()
    exp_intent = str(expected.get("intent") or "").strip().lower()
    if act_intent != exp_intent:
        diffs.append(f"intent: actual='{act_intent}', expected='{exp_intent}'")

    # 2. party_size
    if actual.get("party_size") != expected.get("party_size"):
        diffs.append(f"party_size: actual={actual.get('party_size')}, expected={expected.get('party_size')}")

    # 3. date
    act_date = actual.get("date")
    exp_date = expected.get("date")
    if (act_date is None or exp_date is None) and act_date != exp_date:
        diffs.append(f"date: actual={act_date}, expected={exp_date}")
    elif act_date is not None and exp_date is not None:
        if str(act_date).strip().lower() != str(exp_date).strip().lower():
            diffs.append(f"date: actual='{act_date}', expected='{exp_date}'")

    # 4. time
    if actual.get("time") != expected.get("time"):
        diffs.append(f"time: actual='{actual.get('time')}', expected='{expected.get('time')}'")

    # 5. food_preference
    act_food = sorted([str(x).strip().lower() for x in (actual.get("food_preference") or [])])
    exp_food = sorted([str(x).strip().lower() for x in (expected.get("food_preference") or [])])
    if act_food != exp_food:
        diffs.append(f"food_preference: actual={act_food}, expected={exp_food}")

    return len(diffs) == 0, diffs


def run_multi_turn_tests(dataset_path: str = DATASET_FILE, max_conversations: int = None):
    if not os.path.exists(dataset_path):
        print(f"Error: Dataset file '{dataset_path}' not found.")
        sys.exit(1)

    with open(dataset_path, "r", encoding="utf-8") as f:
        conversations = json.load(f)

    if max_conversations:
        conversations = conversations[:max_conversations]

    print("=" * 70)
    print(f"  MULTI-TURN RESTAURANT BOOKING STATE EVALUATION ({len(conversations)} CONVERSATIONS)")
    print("=" * 70)

    total_turns = 0
    passed_turns = 0
    total_convs = len(conversations)
    passed_convs = 0

    results = []

    for c_idx, conv in enumerate(conversations, 1):
        conv_id = conv.get("conversation_id", f"CONV-{c_idx:03d}")
        title = conv.get("title", "Untitled")
        focus = conv.get("primary_focus", "General")
        turns = conv.get("turns", [])

        print(f"\n[{c_idx}/{total_convs}] {conv_id}: {title} ({focus})")
        print("-" * 70)

        session = BookingState()
        conv_passed = True
        conv_results = {
            "conversation_id": conv_id,
            "title": title,
            "primary_focus": focus,
            "turns": []
        }

        for turn in turns:
            turn_id = turn.get("turn_id")
            msg = turn.get("customer_message", "")
            expected = turn.get("expected_state", {})

            total_turns += 1

            # Process turn through state manager
            actual = session.process_message(msg)

            is_match, diffs = compare_state(actual, expected)
            status = "PASS" if is_match else "FAIL"

            if is_match:
                passed_turns += 1
                print(f"  Turn {turn_id}: [{status}] \"{msg[:45]}...\"" if len(msg) > 45 else f"  Turn {turn_id}: [{status}] \"{msg}\"")
            else:
                conv_passed = False
                print(f"  Turn {turn_id}: [{status}] \"{msg}\"")
                for diff in diffs:
                    print(f"     -> Diff: {diff}")
                print(f"     Actual:   {actual}")
                print(f"     Expected: {expected}")

            conv_results["turns"].append({
                "turn_id": turn_id,
                "message": msg,
                "expected": expected,
                "actual": actual,
                "status": status,
                "diffs": diffs
            })

            time.sleep(1.0)

        if conv_passed:
            passed_convs += 1
            print(f"  -> Result: PASS")
        else:
            print(f"  -> Result: FAIL")

        results.append(conv_results)

    # Summary
    turn_acc = (passed_turns / total_turns * 100) if total_turns > 0 else 0
    conv_acc = (passed_convs / total_convs * 100) if total_convs > 0 else 0

    print("\n" + "=" * 70)
    print("                 MULTI-TURN EVALUATION SUMMARY")
    print("=" * 70)
    print(f"Total Conversations:         {total_convs}")
    print(f"Passed Conversations:        {passed_convs} ({conv_acc:.1f}%)")
    print(f"Total Dialog Turns:          {total_turns}")
    print(f"Passed Turns:                {passed_turns} ({turn_acc:.1f}%)")
    print(f"Results saved to:            '{RESULTS_FILE}'")
    print("=" * 70)

    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    return total_convs, passed_convs, total_turns, passed_turns


if __name__ == "__main__":
    max_c = int(sys.argv[1]) if len(sys.argv) > 1 else None
    run_multi_turn_tests(max_conversations=max_c)
