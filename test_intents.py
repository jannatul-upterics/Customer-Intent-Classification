import os
import sys
import json
import time
import datetime
from intent_classifier import extract_booking_info, resolve_calendar_date

# Ensure utf-8 stdout on Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

DATASET_FILE = "test_dataset.json"
RESULTS_FILE = "test_results.json"

def compare_results(actual: dict, expected: dict) -> bool:
    """
    Compares the actual output with the expected output across all fields:
    - intent
    - party_size
    - date (handles dynamic calendar resolution relative to current environment)
    - time
    - food_preference (canonical snake_case dictionary, excluding unstated non_vegetarian)
    - summary (validates presence, string type, non-emptiness)
    - auxiliary preferences (seating_preference, accessibility_requirement, etc.)
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
        act_str = str(actual_date).strip().lower()
        exp_str = str(expected_date).strip().lower()
        if act_str != exp_str:
            ref_date = datetime.date.today()
            if os.environ.get("REFERENCE_DATE"):
                try:
                    ref_date = datetime.date.fromisoformat(os.environ["REFERENCE_DATE"])
                except Exception:
                    pass
            resolved_act = resolve_calendar_date(act_str, base_date=ref_date)
            resolved_exp = resolve_calendar_date(exp_str, base_date=ref_date)
            if (resolved_act and resolved_exp and resolved_act == resolved_exp) or \
               (resolved_act and resolved_act == exp_str) or \
               (resolved_exp and resolved_exp == act_str):
                pass
            else:
                return False

    # 4. time comparison (string HH:MM or None)
    actual_time = actual.get("time")
    expected_time = expected.get("time")
    if actual_time != expected_time:
        return False

    # 5. food_preference comparison (canonical snake_case keys, excluding unstated non_vegetarian)
    def canonical_diet_tag(t: str) -> str:
        t = str(t).strip().lower()
        if t in ("nut-free", "nut free", "nut_allergy", "nut allergy", "peanut allergy", "peanut-free", "peanut", "nuts"):
            return "nut_allergy"
        if t in ("dairy-free", "dairy free", "dairy_free", "no dairy", "lactose intolerant", "lactose-free"):
            return "dairy_free"
        if t in ("gluten-free", "gluten free", "gluten_free", "no gluten", "celiac", "coeliac", "gluten allergy", "gluten_allergy"):
            return "gluten_free"
        if t in ("veg", "veggie", "vegetarian", "vegetarian food", "meat-free"):
            return "vegetarian"
        if t in ("vegan", "plant-based", "plant based"):
            return "vegan"
        return t

    actual_food_raw = actual.get("food_preference") or {}
    expected_food_raw = expected.get("food_preference") or {}
    if isinstance(actual_food_raw, list):
        actual_food_raw = {str(x).strip().lower(): 1 for x in actual_food_raw}
    if isinstance(expected_food_raw, list):
        expected_food_raw = {str(x).strip().lower(): 1 for x in expected_food_raw}

    actual_food = {canonical_diet_tag(k): v for k, v in actual_food_raw.items() if k != "non_vegetarian"}
    expected_food = {canonical_diet_tag(k): v for k, v in expected_food_raw.items() if k != "non_vegetarian"}

    if actual_food != expected_food:
        return False

    # 6. summary comparison (always present, string, non-empty)
    actual_summary = actual.get("summary")
    if not isinstance(actual_summary, str) or not actual_summary.strip() or actual_summary.strip().lower() == "null":
        return False

    # 7. auxiliary preferences comparison (seating, accessibility, celebration, etc.)
    for pref_key in expected.keys():
        if pref_key in ("intent", "party_size", "date", "time", "food_preference", "summary"):
            continue
        actual_pref = actual.get(pref_key) or {}
        expected_pref = expected.get(pref_key) or {}
        if actual_pref != expected_pref:
            return False

    return True

def run_tests(max_cases: int = None):
    if not os.path.exists(DATASET_FILE):
        print(f"Error: Dataset file '{DATASET_FILE}' not found.")
        sys.exit(1)

    with open(DATASET_FILE, "r", encoding="utf-8") as f:
        test_cases = json.load(f)

    if max_cases is not None:
        test_cases = test_cases[:max_cases]

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
            if "error" in actual and any(err_kw in str(actual["error"]).lower() for err_kw in ("429", "rate limit", "400", "connection error")):
                wait_sec = 2 * (attempt + 1)
                print(f"(API retry, waiting {wait_sec}s, retry {attempt + 1})...", end=" ", flush=True)
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

        time.sleep(1.5)

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
