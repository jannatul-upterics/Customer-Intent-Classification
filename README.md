# Restaurant Booking Information Extraction & Customer Intent Classification

A restaurant booking assistant built in Python that extracts reservation details and tracks customer intent across conversations. Powered by the **Groq Cloud API** (running open-weights models like `openai/gpt-oss-20b`), it parses messy customer messages, normalizes the data, and returns clean, structured JSON ready for booking systems.

---

## 1. Project Overview

What started as an intent classifier has grown into a full reservation assistant that handles both single-message extraction and multi-turn conversation state tracking.

When a customer messages the restaurant, the system:
1. **Identifies what they want:** Categorizes their goal into booking, cancellation, modification, or a general question.
2. **Pulls out key booking details:** Extracts guest count, date, time, and dietary preferences.
3. **Normalizes messy inputs:** Turns words into numbers (*"five"* $\rightarrow `5`$), converts colloquial times to 24-hour format (*"8 PM"* $\rightarrow `"20:00"`$), and maps allergy descriptions to clean tags.
4. **Remembers context:** Keeps track of details across multiple turns so customers can change party sizes, add requirements, or ask questions naturally.
5. **Outputs clean JSON:** Delivers validated JSON with no extra conversational fluff or markdown formatting.

---

## 2. Input and Output Format

### Input
The system accepts natural-language customer messages from chat widgets, SMS, or transcribed calls.

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

| Field | Data Type | Nullable | Description & Practical Purpose |
| :--- | :--- | :---: | :--- |
| **`intent`** | `string` | No | What the customer is trying to do (`"booking"`, `"inquiry"`, `"cancellation"`, or `"modification"`). Used to route the conversation. |
| **`party_size`** | `integer` | Yes | Total number of dining guests. Converted from words to integer digits. Set to `null` if unspecified, ambiguous, or zero. |
| **`date`** | `string` | Yes | Target reservation day (capitalized weekday such as `"Saturday"`) or relative day (`"today"`, `"tomorrow"`, `"tonight"`). Set to `null` if unspecified or invalid. |
| **`time`** | `string` | Yes | Target reservation time strictly in 24-hour `"HH:MM"` format (e.g., `"20:00"`, `"12:30"`). Set to `null` if unspecified or an imprecise wide range. |
| **`food_preference`** | `array[string]` | No | List of normalized dietary requirements or food allergies (e.g., `["vegan", "gluten-free"]`). Always returned as an array, defaulting to `[]` when none are mentioned. |

---

## 4. Extraction & Normalization Behavior

The extraction engine (`intent_classifier.py`) applies practical normalization rules to handle real-world speech:

* **Party Size:** Converts words to numbers (*"five"* $\rightarrow `5`$, *"a couple"* $\rightarrow `2`$, *"myself"* $\rightarrow `1`$). Unrealistic or non-dining counts (like zero people) resolve to `null`.
* **24-Hour Time Conversion:** Converts 12-hour AM/PM and casual times (*"8 PM"* $\rightarrow `"20:00"`$, *"noon"* $\rightarrow `"12:00"`$, *"10:30 AM"* $\rightarrow `"10:30"`$). Single approximate times (*"around 8 PM"*) resolve to that hour (`"20:00"`). Vague time windows (*"between 6 and 9 PM"*, *"evening"*) resolve to `null`.
* **Date Normalization:** Cleans up weekday names and strips leading filler words (*"this Friday"* $\rightarrow `"Friday"`$, *"on Saturday"* $\rightarrow `"Saturday"`). Vague multi-day periods (*"next weekend"*, *"sometime next week"*) or non-existent dates (*"February 31st"*) are safely set to `null`.
* **Dietary Tag Canonicalization:** Standardizes casual phrasing and medical terms into clean operational tags (*"peanut allergy"* $\rightarrow `"nut-free"`$, *"celiac"* $\rightarrow `"gluten-free"`$, *"lactose intolerant"* $\rightarrow `"dairy-free"`$). Always outputs a JSON array, defaulting to `[]` if no preferences were mentioned.
* **Missing Details:** If a customer doesn't specify a field, it cleanly defaults to `null` for `party_size`, `date`, and `time`, and `[]` for `food_preference`.
* **Handling Slang & Typos:** Robustly handles casual expressions (*"me and 7 buddies"* $\rightarrow `8`$) and common typos (*"tbl for 3 peopel tommorow"*).
* **Mid-Sentence Self-Corrections:** Automatically catches when a user corrects themselves in a single breath (*"table for 4... actually make that 6"* $\rightarrow `6`$; *"Thursday, sorry I meant Friday"* $\rightarrow `"Friday"`).
* **No Guessing or Hallucinations:** The system only extracts information explicitly mentioned or clearly implied by the customer—it won't invent dates, times, or guests out of thin air.

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

### 3. Interactive Multi-Turn Session Mode
Run an ongoing interactive dialogue in your terminal, tracking booking state across consecutive turns:
```powershell
python intent_classifier.py --session
```
**Interactive session controls:**
* Type customer messages sequentially to see the updated state after each turn.
* Type `history` to view all past conversation turns.
* Type `reset` to clear the current reservation and start a fresh session.
* Type `exit` or `quit` to end the session.

---

## 8. Multi-Turn Conversation State Management

### 1. What the Prototype Does
In real conversations, people rarely provide every reservation detail in a single sentence. A customer might say *"I'd like a table for 4"*, follow up with *"this Saturday at 8 PM"*, then say *"actually, make it 6"*, and later add *"one person is vegetarian"*.

The **Conversation Context and State Management** system remembers details throughout a multi-turn conversation. Instead of treating each message in isolation or forcing the customer to repeat themselves, it maintains an ongoing booking state—adding new details as they come up, updating modified info, removing cancelled requirements, and shifting intent if the customer changes their mind.

### 2. How the Conversation State is Maintained and Updated
State is managed in memory using the lightweight [`BookingState`](state_manager.py) class, which acts as the single source of truth for an active conversation:

1. **In-Memory State (`BookingState`):**  
   The reservation state is stored as a clean dictionary with 5 core fields:
   ```json
   {
       "intent": "booking",
       "party_size": null,
       "date": null,
       "time": null,
       "food_preference": []
   }
   ```
2. **Context-Aware Updates via the LLM:**  
   When a new message arrives (`session.process_message(message)`), the system passes both the **current state** and the **new customer message** into [`update_booking_state_with_llm()`](intent_classifier.py). The prompt directs the LLM to act as a dialogue state tracker:
   * It checks what changed between the current state and the new message.
   * It updates or adds only the relevant fields.
   * It leaves untouched fields alone so existing booking details aren't lost.
   * It outputs the updated state as a validated JSON object.
3. **Data Cleanup & Turn History:**  
   The updated values pass through [`normalize_booking_data()`](intent_classifier.py) to guarantee consistent formatting (24-hour `"HH:MM"`, lowercase dietary tags, integer party sizes). Every turn is also logged to `state.history` with a timestamp so you can review the full back-and-forth or reset the session anytime.

### 3. Handling Common Conversational Scenarios

The system handles the everyday ways people naturally message a restaurant:

* **Step-by-Step Details:**  
  Customers often share details across multiple messages. The system accumulates slots as they come in (e.g., party size first, date and time second) without losing earlier info.
* **Changing Existing Information:**  
  When a customer changes their mind (*"Actually, make it 6"* or *"Instead, make it 8 PM"*), the system updates just that specific field while keeping the rest of the reservation intact.
* **Adding New Details Later:**  
  If a customer mentions a dietary requirement later in the chat (*"One person is vegetarian"*), it gets added to the state without resetting the party size or time.
* **Removing or Modifying Requirements:**  
  * **Removing a requirement:** If someone changes their mind about a constraint (*"Actually, no dietary requirements"* or *"Scratch that, no allergies"*), the system resets `food_preference` back to `[]`.
  * **Substitutions vs. additions:** The system knows whether a customer wants to replace a requirement or add another. *"Make it vegan instead"* replaces vegetarian with vegan (`["vegan"]`), whereas *"also one vegan"* keeps both (`["vegetarian", "vegan"]`).
* **Changing Intent Mid-Conversation:**  
  If a customer decides to cancel (*"Please cancel our reservation"*) or pivots to asking questions (*"I don't want to book anymore, what time do you close?"*), the system updates the `intent` field (e.g., `"booking"` $\rightarrow$ `"cancellation"` or `"inquiry"`).

### 4. Step-by-Step Example Across Multiple Turns

Here is a realistic example showing how the state changes across 6 consecutive customer turns:

| Turn | Customer Message | Resulting Conversation State | What Happened / State Explanation |
| :---: | :--- | :--- | :--- |
| **1** | `"I'd like a table for 4."` | `{"intent": "booking", "party_size": 4, "date": null, "time": null, "food_preference": []}` | **Initial Booking Started:** Sets `intent: "booking"` and captures `party_size: 4`. Remaining slots stay `null`/empty. |
| **2** | `"This Saturday at 8 PM."` | `{"intent": "booking", "party_size": 4, "date": "Saturday", "time": "20:00", "food_preference": []}` | **Adding Details Step-by-Step:** Adds `date: "Saturday"` and `time: "20:00"` while **retaining** `party_size: 4`. |
| **3** | `"Actually, make it 6."` | `{"intent": "booking", "party_size": 6, "date": "Saturday", "time": "20:00", "food_preference": []}` | **Updating Existing Info:** Updates `party_size` from 4 to 6. Keeps Saturday 20:00 intact. |
| **4** | `"One person is vegetarian."` | `{"intent": "booking", "party_size": 6, "date": "Saturday", "time": "20:00", "food_preference": ["vegetarian"]}` | **Adding a New Detail:** Adds `"vegetarian"` to `food_preference` without affecting any other parameters. |
| **5** | `"Actually, no dietary requirements."` | `{"intent": "booking", "party_size": 6, "date": "Saturday", "time": "20:00", "food_preference": []}` | **Removing a Requirement:** Catches the cancellation phrase and resets `food_preference` to `[]`. |
| **6** | `"Please cancel our reservation."` | `{"intent": "cancellation", "party_size": 6, "date": "Saturday", "time": "20:00", "food_preference": []}` | **Changing Customer Intent:** Switches `intent` to `"cancellation"`, keeping collected details for reference. |

### 5. Running the 10+ Multi-Turn Test Conversations

We included a test suite of 12 realistic multi-turn conversations in [`multi_turn_test_dataset.json`](multi_turn_test_dataset.json), covering all these situations:

| Conversation ID | Conversational Situation / Focus | Turns |
| :--- | :--- | :---: |
| **`CONV-001`** | Information provided step-by-step | 3 |
| **`CONV-002`** | Changing guest count (*"Actually, make it 6"*) | 3 |
| **`CONV-003`** | Changing reservation date (*"Push it to Sunday"*) | 3 |
| **`CONV-004`** | Changing reservation time (*"Earlier at 6:30 PM"*) | 3 |
| **`CONV-005`** | Adding a dietary requirement (*"Two are gluten-free"*) | 3 |
| **`CONV-006`** | Removing a dietary requirement (*"No dietary requirements"*) | 3 |
| **`CONV-007`** | Adding new info while retaining previously collected info | 3 |
| **`CONV-008`** | Multiple parameter changes in the same turn (*"6 people at 8:30 PM"*) | 3 |
| **`CONV-009`** | Conversational / ambiguous correction (*"Not 7, 7:30"*) | 3 |
| **`CONV-010`** | Changing customer intention (*Booking $\rightarrow$ Inquiry / Cancellation*) | 4 |
| **`CONV-011`** | Dietary substitution (*"Make it vegan instead of vegetarian"*) | 3 |
| **`CONV-012`** | Multi-parameter updates (*Date, time, and party size change simultaneously*) | 3 |

#### Run the Multi-Turn Benchmark Evaluation Runner
To execute all 10 benchmark conversations and inspect the resulting state and `PASS`/`FAIL` status after each turn:
```powershell
python test_multi_turn.py 10
```
*Or run the detailed test reporter script:*
```powershell
python run_and_report_10_conversations.py
```

#### Run the Fast Offline Unit Test Suite
To verify core state management operations (additions, updates, deletions, substitutions, and intent transitions) without making LLM API calls:
```powershell
python test_state_management.py
```


---

## 9. Automated Testing & Verification

The project includes automated test runners and benchmark datasets to verify extraction and state tracking accuracy:

* **`test_dataset.json`**: Single-turn benchmark dataset containing 25 test cases covering edge cases.
* **`test_intents.py`**: Single-turn benchmark test runner executing all 25 cases against `extract_booking_info()`.
* **`multi_turn_test_dataset.json`**: Multi-turn benchmark dataset containing 12 realistic conversations covering additions, revisions, cancellations, substitutions, and intent pivots.
* **`test_multi_turn.py`**: Multi-turn conversation evaluation runner.
* **`run_and_report_10_conversations.py`**: Standalone runner for the 10 benchmark conversations with turn-by-turn verification.
* **`test_state_management.py`**: Automated unit test suite verifying state management logic.

### Run the Single-Turn Benchmark Test Suite
```powershell
python test_intents.py
```

### Run the Multi-Turn State Management Test Suite
```powershell
python test_multi_turn.py 10
```
Or run the dedicated 10-conversation evaluation reporter:
```powershell
python run_and_report_10_conversations.py
```

---

## 10. Examples of Supported Scenarios

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

## 11. Project Structure

```text
Customer Intent Classification/
├── .env                                            # Local environment configuration for API key (gitignored)
├── .gitignore                                      # Git ignore rules for virtual environments and secrets
├── requirements.txt                                # Python project dependencies
├── README.md                                       # Project documentation
│
├── intent_classifier.py                            # Main live LLM classifier & dialogue state tracking engine
├── state_manager.py                                # In-memory conversation state management class (BookingState)
├── test_intents.py                                 # Single-turn benchmark test runner & evaluator
├── test_state_management.py                        # Automated unit tests for conversation state transitions
├── test_multi_turn.py                              # Multi-turn benchmark evaluation runner
├── run_and_report_10_conversations.py              # Standalone runner for the 10 benchmark conversations
│
├── test_dataset.json                               # 25 single-turn benchmark test cases
├── multi_turn_test_dataset.json                    # 12 realistic multi-turn benchmark conversations
├── test_results.json                               # Single-turn test execution results
├── multi_turn_test_results.json                    # Multi-turn test execution results
├── eval_run_10_convs.json                          # Detailed turn-by-turn verification logs
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

## 12. Practical Notes & Assumptions

1. **Two Ways to Use the Pipeline:** You can either run single-message extraction directly with `extract_booking_info()`, or use `BookingState` with `update_booking_state_with_llm()` when you need to maintain conversational context across multiple turns.
2. **Groq API Rate Limits:** Free-tier Groq accounts enforce token-per-minute (TPM) limits. Our test scripts include built-in pauses (`1.0s`–`2.0s`) and automatic retry backoff if an HTTP 429 is encountered.
3. **Deterministic Responses:** We lock `temperature` to `0.0` and turn on JSON response mode so the extraction and state updates stay consistent and predictable across runs.
4. **Active Internet Connection Required:** Because LLM calls are routed live to Groq Cloud API endpoints, you will need an active internet connection to run the extraction and multi-turn tests.
