# Restaurant Function-Calling Prototype

A beginner-friendly Python prototype designed as the foundation for an LLM-based restaurant function-calling assistant.

This project focuses solely on defining the core business actions, standardizing input parameters, and structuring expected outputs before connecting an LLM.

---

## 1. Project Structure

```
restaurant_prototype/
├── actions.py           # Core Python functions (business logic & schemas)
├── main.py              # Standalone demonstration runner (no LLM required)
├── test_actions.py      # Automated unit tests for all 4 functions
├── requirements.txt     # Dependency specifications
└── README.md            # Project documentation and specifications
```

---

## 2. Supported Actions & Specifications

### 1. Check Availability (`check_availability`)
* **Purpose**: Determine whether a table is free for a given date, time, and guest count.
* **Input Parameters**:
  * `date` (*string, required*): The requested reservation date or day (e.g., `"2026-09-12"`, `"Saturday"`, `"tomorrow"`).
  * `time` (*string, required*): The requested reservation time (e.g., `"20:00"`, `"19:30"`, `"8 PM"`).
  * `number_of_guests` (*integer, required*): Total dining guests.
* **Expected Output**:
  ```json
  {
    "status": "success",
    "action": "check_availability",
    "available": true,
    "date": "2026-09-12",
    "time": "20:00",
    "number_of_guests": 4,
    "message": "A table for 4 guests is available on 2026-09-12 at 20:00."
  }
  ```

---

### 2. Create Booking (`create_booking`)
* **Purpose**: Confirm a new reservation and issue a unique booking reference.
* **Input Parameters**:
  * `customer_name` (*string, required*): The full name of the customer.
  * `date` (*string, required*): Reservation date or day.
  * `time` (*string, required*): Reservation time.
  * `number_of_guests` (*integer, required*): Total dining guests.
* **Expected Output**:
  ```json
  {
    "status": "success",
    "action": "create_booking",
    "booking_id": "RES-5821",
    "customer_name": "Jannatul",
    "date": "2026-09-12",
    "time": "20:00",
    "number_of_guests": 4,
    "message": "Booking confirmed for Jannatul (4 guests) on 2026-09-12 at 20:00. Booking ID: RES-5821."
  }
  ```

---

### 3. Modify Booking (`modify_booking`)
* **Purpose**: Update an existing reservation's date, time, or guest count.
* **Input Parameters**:
  * `booking_id` (*string, required*): Existing reservation identifier (e.g., `"RES-5821"`).
  * `new_date` (*string, optional*): Updated reservation date.
  * `new_time` (*string, optional*): Updated reservation time.
  * `new_number_of_guests` (*integer, optional*): Updated guest count.
* **Expected Output**:
  ```json
  {
    "status": "success",
    "action": "modify_booking",
    "booking_id": "RES-5821",
    "updated_fields": {
      "number_of_guests": 6,
      "time": "20:30"
    },
    "message": "Booking RES-5821 successfully updated with: {'number_of_guests': 6, 'time': '20:30'}."
  }
  ```

---

### 4. Cancel Booking (`cancel_booking`)
* **Purpose**: Cancel an active reservation using its reference ID.
* **Input Parameters**:
  * `booking_id` (*string, required*): Reservation identifier to cancel.
* **Expected Output**:
  ```json
  {
    "status": "success",
    "action": "cancel_booking",
    "booking_id": "RES-5821",
    "message": "Booking RES-5821 has been successfully cancelled."
  }
  ```

---

## 3. How to Run

### Run the Standalone Demo
```bash
python main.py
```

### Run the Unit Tests
```bash
python -m unittest test_actions.py
```

---

## 4. Next Step: Connecting the LLM
When ready to integrate an LLM:
1. Wrap each function in an OpenAI/Groq tool schema (`{"type": "function", "function": {...}}`).
2. Pass the tools array in the API call with `tool_choice="auto"`.
3. Have the LLM inspect the customer message, pick the tool, and pass extracted arguments to `actions.py`.
