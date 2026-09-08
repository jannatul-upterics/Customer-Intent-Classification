# Restaurant Booking Information Extraction & Customer Intent Classification

A production-ready Natural Language Understanding (NLU) system for restaurant reservation conversations. The application uses the **Groq Cloud API** with open-weights large language models to analyze incoming customer messages, identify conversational intent, and extract structured booking parameters into strictly formatted, machine-readable JSON.

---

## 1. Project Overview

Originally designed for fine-grained intent classification, the system has been extended into an end-to-end **Joint Intent Detection and Slot Filling (Information Extraction)** pipeline. 

When a customer sends an unconstrained natural-language reservation request, the system:
1. Identifies the user's primary goal (e.g., booking, cancellation, modification, or inquiry).
2. Extracts operational reservation details: party size, target date, reservation time, and dietary requirements.
3. Normalizes all parameters (word numbers to integers, 12h times to 24-hour format, canonical dietary tags).
4. Returns a strictly structured, validated JSON object with zero conversational filler or markdown wrappers.

---

## 2. Input and Output Format

### Input
The system accepts natural-language customer messages received via text, chat interfaces, or voice transcripts.

**Example Input:**
```text
I'd like a table for five this Saturday at 8 PM. One person is vegetarian.
```

### Output
The system outputs a valid JSON object containing exactly five fields:

```json
{
  "intent": "booking",
  "party_size": 5,
  "date": "Saturday",
  "time": "20:00",
  "food_preference": [
    "vegetarian"
  ]
}
```

---

## 3. Output Fields Specification

| Field | Data Type | Nullable | Description & Operational Purpose |
| :--- | :--- | :---: | :--- |
| **`intent`** | `string` | No | Primary conversational objective (`"booking"`, `"inquiry"`, `"cancellation"`, or `"modification"`). Used for workflow routing. |
| **`party_size`** | `integer` | Yes | Total number of dining guests. Converted from words to integer digits. Set to `null` if unspecified, ambiguous, or zero. |
| **`date`** | `string` | Yes | Target reservation day (capitalized weekday such as `"Saturday"`) or relative day (`"today"`, `"tomorrow"`, `"tonight"`). Set to `null` if unspecified or invalid. |
| **`time`** | `string` | Yes | Target reservation time strictly in 24-hour `"HH:MM"` format (e.g., `"20:00"`, `"12:30"`). Set to `null` if unspecified or an imprecise wide range. |
| **`food_preference`** | `array[string]` | No | List of normalized dietary requirements or food allergies (e.g., `["vegan", "gluten-free"]`). Always returned as an array, defaulting to `[]` when none are mentioned. |

---

## 4. Extraction & Normalization Behavior

The extraction engine (`intent_classifier.py`) implements strict extraction and normalization heuristics:

* **Party Size Parsing:** Converts cardinal number words into integer values (*"five"* $\rightarrow `5`$, *"a couple"* $\rightarrow `2`$, *"myself"* $\rightarrow `1`$). Unrealistic or non-dining counts (e.g., zero people) resolve to `null`.
* **24-Hour Time Conversion:** Converts 12-hour AM/PM and colloquial times (*"8 PM"* $\rightarrow `"20:00"`$, *"noon"* $\rightarrow `"12:00"`$, *"10:30 AM"* $\rightarrow `"10:30"`$). Approximate single times (*"around 8 PM"*) resolve to that hour (`"20:00"`). Wide ambiguous intervals (*"between 6 and 9 PM"*, *"evening"*) resolve to `null`.
* **Date Normalization:** Canonicalizes weekday names and strips leading determiners (*"this Friday"* $\rightarrow `"Friday"`$, *"on Saturday"* $\rightarrow `"Saturday"`$). Indefinite multi-day periods (*"next weekend"*, *"sometime next week"*) and non-existent calendar dates (*"February 31st"*) are safely mapped to `null`.
* **Dietary Tag Canonicalization:** Standardizes informal phrases and medical terms into canonical operational tags (*"peanut allergy"* $\rightarrow `"nut-free"`$, *"celiac"* $\rightarrow `"gluten-free"`$, *"lactose intolerant"* $\rightarrow `"dairy-free"`$). Always outputs a JSON array, defaulting to `[]` if no preferences are mentioned.
* **Missing Information Handling:** Missing or indeterminate parameters are explicitly assigned `null` (`party_size`, `date`, `time`), while `food_preference` defaults to `[]`.
* **Conversational Resilience:** Robustly parses informal speech, slang (*"me and 7 buddies"* $\rightarrow `8`$), and grammatical errors or typos (*"tbl for 3 peopel tommorow"*).
* **Mid-Sentence Self-Corrections:** Automatically detects user corrections and adopts the latest stated value (*"table for 4... actually make that 6"* $\rightarrow `6`$; *"Thursday, sorry I meant Friday"* $\rightarrow `"Friday"`$).
* **No Information Invention:** The system strictly adheres to details provided or clearly implied by the customer, preventing hallucinations.

---

## 5. API Configuration

The application communicates with the **Groq Cloud API** using an OpenAI-compatible interface:

* **Endpoint:** `https://api.groq.com/openai/v1/chat/completions`
* **Default Model:** `openai/gpt-oss-20b`
* **Automated Failover Models:** `groq/compound`, `qwen/qwen3.6-27b`
* **Inference Settings:** `temperature: 0.0` (deterministic), `response_format: {"type": "json_object"}`

### Secure API Key Management
The API key is loaded dynamically at runtime via `python-dotenv`. It is **never hardcoded** in the codebase.

A pre-configured `.env` file is **already provided with this project**. 

Before running the application, make sure the provided `.env` file is placed directly inside the **project root directory (`Customer Intent Classification/`)**:

```text
Customer Intent Classification/
├── .env      <-- Place the provided .env file here
├── intent_classifier.py
...
```

Inside the `.env` file, the configuration is stored as:
```env
GROQ_API_KEY="your_api_key_here"
```

---

## 6. Installation & Setup

### 1. Prerequisites
* **Python 3.8+** installed on your system.

### 2. Clone or Open the Project
Navigate to the project directory:
```powershell
cd "Customer Intent Classification"
```

### 3. (Optional) Create a Virtual Environment
```powershell
# Create virtual environment
python -m venv venv

# Activate on Windows (PowerShell)
venv\Scripts\Activate.ps1

# Activate on Linux/macOS
source venv/bin/activate
```

### 4. Install Dependencies
Install the required packages from `requirements.txt`:
```powershell
pip install -r requirements.txt
```

### 5. Groq API Key & Credentials
A pre-configured `.env` file is **already provided with this project**. Before running the application, make sure the provided `.env` file is placed directly inside the project root directory (`Customer Intent Classification/`).

---

## 7. Running the Application

### 1. Interactive Command Line Mode
Run the program:
```powershell
python intent_classifier.py
```
Type any customer message and press **Enter**:
```text
I'd like a table for five this Saturday at 8 PM. One person is vegetarian.
```
The program outputs the formatted JSON result:
```json
{
    "intent": "booking",
    "party_size": 5,
    "date": "Saturday",
    "time": "20:00",
    "food_preference": [
        "vegetarian"
    ]
}
```

### 2. Pipe Input Mode (Ideal for Scripting & Automation)
Pipe customer text directly into the script:
```powershell
"I'd like a table for five this Saturday at 8 PM. One person is vegetarian." | python intent_classifier.py
```

---

## 8. Automated Testing & Verification

The project includes an automated test runner and benchmark dataset to verify extraction accuracy across diverse edge cases:

* **`test_dataset.json`**: Benchmark dataset containing 25 test cases covering varied party sizes, 12h/24h time formats, relative dates, multiple food preferences, typos, slang, self-corrections, ambiguous dates, and sparse/missing inputs.
* **`test_intents.py`**: Automated test runner. Executes all 25 test cases against the live LLM extraction engine, performs multi-field validation, handles API rate limits with exponential backoff, and saves results.
* **`test_results.json`**: Automatically generated log recording input messages, expected outputs, actual model outputs, and PASS/FAIL statuses.
* **`reports/Customer_Intent_Test_Report.docx`**: Formal benchmark evaluation test report detailing testing methodology, baseline error analysis, prompt optimizations, and final accuracy metrics.

### Run the Benchmark Test Suite
Execute the test runner:
```powershell
python test_intents.py
```

**Benchmark Summary:**
```text
============================================================
      RESTAURANT BOOKING EXTRACTION EVALUATION SUMMARY
============================================================
Total Test Cases:            25
Correctly Processed (PASS):   25
Incorrectly Processed (FAIL): 0
Accuracy:                    100.00%
Results saved to:            'test_results.json'
============================================================
```

---

## 9. Examples of Supported Scenarios

### 1. Complete Booking Request
**Input:** `"I'd like a table for five this Saturday at 8 PM. One person is vegetarian."`  
**Output:**
```json
{
    "intent": "booking",
    "party_size": 5,
    "date": "Saturday",
    "time": "20:00",
    "food_preference": ["vegetarian"]
}
```

### 2. Multiple Dietary Preferences
**Input:** `"Table for 4 on Friday at 19:30. Two of us are vegan and one is gluten-free."`  
**Output:**
```json
{
    "intent": "booking",
    "party_size": 4,
    "date": "Friday",
    "time": "19:30",
    "food_preference": ["vegan", "gluten-free"]
}
```

### 3. Missing Information (Handling `null`)
**Input:** `"Looking to reserve a table for six this Sunday evening. Not sure about the exact time yet."`  
**Output:**
```json
{
    "intent": "booking",
    "party_size": 6,
    "date": "Sunday",
    "time": null,
    "food_preference": []
}
```

### 4. Slang and Colloquial Language
**Input:** `"Hey mate, gonna need a spot for me and 7 buddies this Thursday around 8 PM, all halal meat please."`  
**Output:**
```json
{
    "intent": "booking",
    "party_size": 8,
    "date": "Thursday",
    "time": "20:00",
    "food_preference": ["halal"]
}
```

### 5. Self-Correction Mid-Message
**Input:** `"I'd like to book a table for 4... actually wait, make that 6 people for this Saturday at 8 PM. No food restrictions."`  
**Output:**
```json
{
    "intent": "booking",
    "party_size": 6,
    "date": "Saturday",
    "time": "20:00",
    "food_preference": []
}
```

---

## 10. Project Structure

```text
Customer Intent Classification/
├── .env                                            # Local environment configuration for API key (gitignored)
├── .gitignore                                      # Git ignore rules for virtual environments and secrets
├── requirements.txt                                # Python project dependencies
├── README.md                                       # Project documentation
│
├── intent_classifier.py                            # Main live LLM classifier & booking extraction program
├── test_intents.py                                 # Automated benchmark test runner & accuracy evaluator
├── test_dataset.json                               # 25 benchmark test cases covering edge cases
├── test_results.json                               # Automatically generated test execution results
│
├── reports/
│   └── Customer_Intent_Test_Report.docx            # Formal Word (.docx) benchmark test report
│
├── Customer_Intent_Analysis.xlsx                   # Reference dataset: 14 conversations & 64 intent categories
├── Customer_Intent_Analysis_Report.docx            # Reference report: dialogue taxonomy & conversation analysis
├── Customer_Intent_Classification_Test_Report.docx # Reference report: legacy classification test results
├── Intent Identification.docx                      # Reference notes: conversational intent guidelines
├── Realistic_Restaurant_Booking_Conversations.docx # Reference scripts: multi-turn dining dialogues
└── Restaurant_Booking_Conversations_Reference.docx # Reference guide: annotated dialogue turns
```

---

## 11. Important Notes & Assumptions

1. **Single-Message Analysis:** The extraction program processes individual customer messages independently. Multi-turn dialogue state tracking is designed to be coordinated by an upstream conversational manager.
2. **API Rate Limits:** Groq free-tier accounts enforce token-per-minute (TPM) limits. `test_intents.py` includes pacing delays (`1.0s`) and automatic exponential backoff retries to prevent HTTP 429 throttling.
3. **Deterministic Output:** Temperature is fixed to `0.0` with JSON mode enabled to ensure consistent, reproducible slot extraction.
4. **Internet Connectivity:** Live network access is required to communicate with Groq Cloud API endpoints.
