# Customer Intent Classification

A clean, production-ready Customer Intent Classification system for restaurant table-booking conversations. The application uses the **Groq API** with open-weights language models to analyze incoming customer messages and classify their primary intent into strictly formatted, machine-readable JSON.

---

## Features

* **LLM-Powered Classification:** Connects to the high-speed Groq API (`openai/gpt-oss-20b` with fallback to `groq/compound`) for fast, accurate intent recognition.
* **Strict JSON Output:** Produces pure, machine-readable JSON (`{"intent": "..."}`) with no explanatory text or markdown code fences outside JSON.
* **64-Category Restaurant Taxonomy:** Accurately maps utterances across 64 specialized categories covering new bookings, rescheduling, cancellations, dietary restrictions, severe allergies, and venue logistics.
* **Whitelist Validation:** Uses Python's standard `json` module to parse and validate every prediction against an approved intent set.
* **Resilient HTTP Communication:** Built with Python's standard `requests` library for reliable networking across Windows, Linux, and macOS.
* **Structured Error Handling:** Automatically catches missing keys, invalid credentials (HTTP 401), rate limits (HTTP 429), and connection issues, returning formatted JSON errors.

---

## Technologies Used

* **Python 3.8+**
* **Groq Cloud API** (Fast LLM inference using open-weights models)
* **Requests** (HTTP client for API communication)
* **python-dotenv** (Environment variable and `.env` file management)
* **OpenPyXL** & **python-docx** (Dataset curation, Excel mapping, and report processing)

---

## Example Input & Output

### 1. Table Booking
**Input:**
```text
hello book table at 7:00 pm
```
**Output:**
```json
{"intent": "Initial Table Booking"}
```

### 2. Reservation Cancellation
**Input:**
```text
cancel my booking please
```
**Output:**
```json
{"intent": "Cancelling the Booking"}
```

### 3. Food Allergy Declaration
**Input:**
```text
My nephew has a severe peanut allergy. Is peanut oil used in the kitchen?
```
**Output:**
```json
{"intent": "Reporting Severe Peanut Allergy"}
```

### 4. Wi-Fi Inquiry
**Input:**
```text
what is your wifi password?
```
**Output:**
```json
{"intent": "Asking for Wi-Fi Password"}
```

### 5. Error Response (e.g., Missing Key)
**Output:**
```json
{"error": "GROQ_API_KEY is not set. Please set your Groq key before running."}
```

---

## Project Structure

```text
Customer Intent Classification/
├── .env                                            # Local API key configuration (gitignored)
├── .gitignore                                      # Git ignore rules for secrets, cache, and scratch files
├── requirements.txt                                # Project dependencies
├── README.md                                       # Project documentation
│
├── intent_classifier.py                            # Main live LLM classifier using Groq API
│
├── Customer_Intent_Analysis.xlsx                   # Master dataset: 14 conversations & 64 intent categories
├── Customer_Intent_Analysis_Report.docx            # Detailed taxonomy and intent analysis report (Word)
├── Customer_Intent_Classification_Test_Report.docx # Benchmark evaluation test report (Word)
├── Realistic_Restaurant_Booking_Conversations.docx # 14 realistic multi-turn booking dialogues (Word)
└── Restaurant_Booking_Conversations_Reference.docx # Dialogue reference guide with turn annotations (Word)
```

---

## Installation & Setup

### 1. Clone or Open the Project
Navigate to the project directory in your terminal or PowerShell:
```powershell
cd "Customer Intent Classification"
```

### 2. (Optional) Create a Virtual Environment
```powershell
# Create virtual environment
python -m venv venv

# Activate on Windows (PowerShell)
venv\Scripts\Activate.ps1

# Activate on Linux/macOS
source venv/bin/activate
```

### 3. Install Dependencies
Install the required packages using `pip`:
```powershell
pip install -r requirements.txt
```

---

## Groq API Key

A pre-configured `.env` file is **already provided with this project**. 

Before running the application, make sure the provided `.env` file is placed directly inside the **project root directory (`Customer Intent Classification/`)**:

```text
Customer Intent Classification/
├── .env      <-- Place the provided .env file here
├── intent_classifier.py
...
```

---

## How to Run

### 1. Interactive Command Line Mode
Run the classifier:
```powershell
python intent_classifier.py
```
Type any customer message and press **Enter**:
```text
hello book table at 7:00 pm
```
The program prints the validated JSON response:
```json
{"intent": "Initial Table Booking"}
```

### 2. Pipe Input Mode (Ideal for Automated Testing)
Pipe customer text directly into the script:
```powershell
"cancel my reservation please" | python intent_classifier.py
```

---

## How Intent Classification Works

```text
Customer Message
       │
       ▼
Python Program (intent_classifier.py)
       │  - Captures input via input().strip()
       │  - Loads GROQ_API_KEY from .env or environment
       ▼
System Prompt & Rules
       │  - Injects definitions for all 64 allowed categories
       │  - Enforces JSON output: {"intent": "..."}
       ▼
Groq API Call
       │  - Primary Model: openai/gpt-oss-20b
       │  - Fallback Models: groq/compound, qwen/qwen3.6-27b
       │  - Response Format: {"type": "json_object"}
       │  - Temperature: 0.0 (deterministic)
       ▼
Validation & Parsing
       │  - Parses response using Python's json module
       │  - Verifies that "intent" exists and matches the allowed list
       ▼
Final JSON Output
```

1. **Input Capture:** Reads customer text from the command line using `input().strip()`.
2. **Credential Loading:** Resolves the API key from `.env` or system environment variables.
3. **Prompt Construction:** Combines the user utterance with a domain-specific system prompt containing the 64 allowed categories and classification instructions.
4. **LLM Inference:** Sends an HTTP POST request to Groq's chat completions endpoint in JSON mode with temperature set to 0.0.
5. **JSON Parsing & Whitelist Check:** Validates that the returned payload is valid JSON and that the classified intent exists in the 64-category taxonomy.
6. **Output Generation:** Prints strictly formatted JSON to standard output.

---

## Troubleshooting & Common Errors

| Error Message | Cause | Solution |
| :--- | :--- | :--- |
| `{"error": "GROQ_API_KEY is not set..."}` | Missing API key. | Ensure the provided `.env` file is placed in the project root directory (`Customer Intent Classification/`). |
| `{"error": "API error (401): Invalid API Key"}` | API key is invalid or revoked. | Generate a fresh key at [console.groq.com/keys](https://console.groq.com/keys). |
| `{"error": "API error (429): Rate limit reached..."}` | Free tier token-per-minute (TPM) limit reached. | Wait a few seconds before submitting the next message. |
| `{"error": "API request failed: Connection error..."}` | Network connection issue or DNS failure. | Verify your internet connection. |
| `{"error": "Customer message cannot be empty."}` | Enter pressed without typing text. | Enter a valid customer utterance. |

---
