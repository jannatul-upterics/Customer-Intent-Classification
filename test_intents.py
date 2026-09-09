import os
import sys
import json
import time
from intent_classifier import extract_booking_info

DATASET_FILE = "test_dataset.json"
RESULTS_FILE = "test_results.json"

def compare_results(actual: dict, expected: dict) -> bool:
    """
    Compares the actual output with the expected output across all 5 fields:
    - intent
    - party_size
    - date
    - time
    - food_preference
    """
    if not isinstance(actual, dict):
        return False

    # 1. intent comparison (case-insensitive string)
    actual_intent = str(actual.get("intent") or "").strip().lower()
    expected_intent = str(expected.get("intent") or "").strip().lower()
    if actual_intent != expected_intent:
        return False

    # 2. party_size comparison (integer or None)
    if actual.get("party_size") != expected.get("party_size"):
        return False

    # 3. date comparison (case-insensitive string or None)
    actual_date = actual.get("date")
    expected_date = expected.get("date")
    if actual_date is None or expected_date is None:
        if actual_date != expected_date:
            return False
    else:
        if str(actual_date).strip().lower() != str(expected_date).strip().lower():
            return False

    # 4. time comparison (string HH:MM or None)
    actual_time = actual.get("time")
    expected_time = expected.get("time")
    if actual_time != expected_time:
        return False

    # 5. food_preference comparison (normalized list of tags, order-agnostic)
    actual_food = [str(x).strip().lower() for x in (actual.get("food_preference") or [])]
    expected_food = [str(x).strip().lower() for x in (expected.get("food_preference") or [])]
    if sorted(actual_food) != sorted(expected_food):
        return False

    return True

def run_tests():
    if not os.path.exists(DATASET_FILE):
        print(f"Error: Dataset file '{DATASET_FILE}' not found.")
        sys.exit(1)

    with open(DATASET_FILE, "r", encoding="utf-8") as f:
        test_cases = json.load(f)[:20]

    print(f"Loaded {len(test_cases)} test cases from '{DATASET_FILE}'. Starting execution...\n")
    results = []
    passed_count = 0

    for idx, tc in enumerate(test_cases, 1):
        tc_id = tc.get("id", f"TC{idx:03d}")
        input_msg = tc.get("input", "")
        expected = tc.get("expected", {})

        print(f"[{idx}/{len(test_cases)}] Running {tc_id}...", end=" ", flush=True)

        # Call live extraction with retry on temporary rate limit
        max_retries = 5
        actual = None
        for attempt in range(max_retries):
            actual = extract_booking_info(input_msg)
            if "error" in actual and ("429" in str(actual["error"]) or "rate limit" in str(actual["error"]).lower()):
                wait_sec = 5 * (attempt + 1)
                print(f"(Rate limit, waiting {wait_sec}s, retry {attempt + 1})...", end=" ", flush=True)
                time.sleep(wait_sec)
                continue
            break

        is_correct = compare_results(actual, expected)
        result_status = "PASS" if is_correct else "FAIL"

        if is_correct:
            passed_count += 1
            print(f"PASS")
        else:
            print(f"FAIL")
            print(f"    Expected: {expected}")
            print(f"    Actual:   {actual}")

        results.append({
            "id": tc_id,
            "input": input_msg,
            "expected": expected,
            "actual": actual,
            "result": result_status
        })

        time.sleep(1.0)

    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4)

    total_count = len(test_cases)
    incorrect_count = total_count - passed_count
    accuracy = (passed_count / total_count * 100) if total_count > 0 else 0

    print(f"\n" + "=" * 60)
    print(f"      RESTAURANT BOOKING EXTRACTION EVALUATION SUMMARY")
    print(f"=" * 60)
    print(f"Total Test Cases:            {total_count}")
    print(f"Correctly Processed (PASS):   {passed_count}")
    print(f"Incorrectly Processed (FAIL): {incorrect_count}")
    print(f"Accuracy:                    {accuracy:.2f}%")
    print(f"Results saved to:            '{RESULTS_FILE}'")
    print(f"=" * 60)

    return total_count, passed_count, incorrect_count, accuracy

if __name__ == "__main__":
    run_tests()
