import os
import sys
import json
import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Allowed Intent Set (Exact 64 Categories)
# ---------------------------------------------------------------------------
ALLOWED_INTENTS = {
    "Accepting Adjusted Time",
    "Accepting Alternative Time",
    "Accepting Cake Plating Fee",
    "Acknowledging Table Check",
    "Adding Dietary & Allergy Needs",
    "Asking About Deposit Policy",
    "Asking About Group Booking Rules",
    "Asking About Outside Cake Policy",
    "Asking About Parking",
    "Asking for Flexible Seating",
    "Asking for Wi-Fi Password",
    "Asking for Zero-Guest Table",
    "Booking for a Special Occasion",
    "Booking with Vague Time",
    "Cancelling the Booking",
    "Changing Date & Meal Time",
    "Changing Guest Count",
    "Changing Seating Preference",
    "Checking Dining Room Hours",
    "Confirming Booking Details",
    "Confirming No Allergies",
    "Confirming Party Size & Time",
    "Confirming Preferred Time",
    "Correcting Date & Stating Occasion",
    "Correcting Reservation Date",
    "Decreasing Guest Count",
    "Disputing Restaurant Policy",
    "Dropping Pets and Bags Request",
    "Ending Call to Call Back",
    "Ending Request & Asking for Email",
    "Explaining Luggage and Pets",
    "Giving Confused Date Info",
    "Giving Date, Time & Headcount",
    "Increasing Guest Count",
    "Initial Table Booking",
    "Inquiring About Halal Food",
    "Inquiring About Vegan Menu",
    "Inquiring About Weekend Table",
    "Inquiring About Wheelchair Access",
    "Making Ambiguous Request",
    "Offering Multiple Times",
    "Ordering Delivery",
    "Pausing the Reservation",
    "Providing Contact Information",
    "Providing Customer Name",
    "Providing Date",
    "Providing Guest Count",
    "Providing Invalid Date",
    "Providing Name & Contact",
    "Providing Name & Phone",
    "Providing Preferred Time",
    "Pushing Reservation Time Back",
    "Reporting Severe Gluten Allergy",
    "Reporting Severe Peanut Allergy",
    "Requesting Birthday Note",
    "Requesting Booth & Dietary Info",
    "Requesting High Chair & Space",
    "Requesting Occasion Seating",
    "Requesting Patio Seating",
    "Requesting Unrealistic Guest Count",
    "Requesting Unreasonable Table Setup",
    "Requesting Work Booth & Outlet",
    "Selecting Specific Time",
    "Switching to Table Booking"
}

# ---------------------------------------------------------------------------
# Improved System Prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are a customer intent classification system for a restaurant table-booking assistant.

Your task is to identify the single primary intent of the customer's message.

You must classify the message using ONLY the following allowed intents:

- Accepting Adjusted Time
- Accepting Alternative Time
- Accepting Cake Plating Fee
- Acknowledging Table Check
- Adding Dietary & Allergy Needs
- Asking About Deposit Policy
- Asking About Group Booking Rules
- Asking About Outside Cake Policy
- Asking About Parking
- Asking for Flexible Seating
- Asking for Wi-Fi Password
- Asking for Zero-Guest Table
- Booking for a Special Occasion
- Booking with Vague Time
- Cancelling the Booking
- Changing Date & Meal Time
- Changing Guest Count
- Changing Seating Preference
- Checking Dining Room Hours
- Confirming Booking Details
- Confirming No Allergies
- Confirming Party Size & Time
- Confirming Preferred Time
- Correcting Date & Stating Occasion
- Correcting Reservation Date
- Decreasing Guest Count
- Disputing Restaurant Policy
- Dropping Pets and Bags Request
- Ending Call to Call Back
- Ending Request & Asking for Email
- Explaining Luggage and Pets
- Giving Confused Date Info
- Giving Date, Time & Headcount
- Increasing Guest Count
- Initial Table Booking
- Inquiring About Halal Food
- Inquiring About Vegan Menu
- Inquiring About Weekend Table
- Inquiring About Wheelchair Access
- Making Ambiguous Request
- Offering Multiple Times
- Ordering Delivery
- Pausing the Reservation
- Providing Contact Information
- Providing Customer Name
- Providing Date
- Providing Guest Count
- Providing Invalid Date
- Providing Name & Contact
- Providing Name & Phone
- Providing Preferred Time
- Pushing Reservation Time Back
- Reporting Severe Gluten Allergy
- Reporting Severe Peanut Allergy
- Requesting Birthday Note
- Requesting Booth & Dietary Info
- Requesting High Chair & Space
- Requesting Occasion Seating
- Requesting Patio Seating
- Requesting Unrealistic Guest Count
- Requesting Unreasonable Table Setup
- Requesting Work Booth & Outlet
- Selecting Specific Time
- Switching to Table Booking

Intent Definitions:
- Accepting Adjusted Time: Customer accepts a newly proposed table time after requesting an adjustment, delay, or postponement (e.g., '1:45 PM is perfect! That gives us breathing room').
- Accepting Alternative Time: Customer accepts an alternative time slot offered by the restaurant because the originally requested time was fully booked (e.g., 'Yes, 8:30 is fine').
- Accepting Cake Plating Fee: Customer agrees to the restaurant's outside cake plating/cutting fee and may request celebratory service details like candles.
- Acknowledging Table Check: Customer gives brief conversational consent for the assistant to check table inventory (e.g., 'Okay', 'Go ahead').
- Adding Dietary & Allergy Needs: Customer informs staff of both dietary preferences (e.g., vegetarian) and medical allergies (e.g., nuts) in one message.
- Asking About Deposit Policy: Customer inquires about or reacts with hesitation to credit card deposit requirements for large parties.
- Asking About Group Booking Rules: Customer inquires about lead times, policies, or event manager contacts for large group reservations.
- Asking About Outside Cake Policy: Customer asks whether they are permitted to bring a personal cake and checks associated plating fees.
- Asking About Parking: Customer inquires about parking facilities, dedicated parking lots, or valet options.
- Asking for Flexible Seating: Customer asks if the restaurant can hold an undecided, floating headcount range (e.g., 'anywhere from 8 to 12 people') or variable tables.
- Asking for Wi-Fi Password: Customer asks for the venue's guest Wi-Fi credentials or internet connectivity details.
- Asking for Zero-Guest Table: Customer explicitly requests a table for 'zero people' (typically intending to store luggage, equipment, or pets).
- Booking for a Special Occasion: Customer initiates a booking explicitly mentioning a celebration, milestone, or special event (e.g., birthday, anniversary).
- Booking with Vague Time: Customer gives an imprecise, approximate dining time (e.g., 'sometime after 8, around 8-ish', '7:30ish').
- Cancelling the Booking: Customer explicitly terminates the reservation process, rejects conditions, and states they will not book or will go elsewhere.
- Changing Date & Meal Time: Customer modifies both the target day and the meal period (e.g., switching from Saturday lunch to Sunday dinner).
- Changing Guest Count: Customer corrects a miscount or amends a previously stated party size without explicit directional increase/decrease verbs (e.g., 'actually seven people, not six').
- Changing Seating Preference: Customer changes their seating preference (e.g., switching from outdoor patio to indoor window table due to weather).
- Checking Dining Room Hours: Customer inquires whether the dine-in dining room is open tonight upon learning telephone delivery is unavailable.
- Confirming Booking Details: Customer confirms that final summarized reservation details repeated by the assistant are accurate (e.g., 'Yes, that's correct').
- Confirming No Allergies: Customer clarifies that no members of the party have dietary restrictions or allergies (e.g., 'No, neither of us has allergies', 'Nope, we eat everything').
- Confirming Party Size & Time: Customer confirms a historical or inferred headcount and dining time together (e.g., 'Yeah, exactly, 8 people at 9 PM').
- Confirming Preferred Time: Customer re-confirms that an originally requested dining time is still desired after resolving unrelated detours.
- Correcting Date & Stating Occasion: Customer rectifies a mistaken booking date and simultaneously explains the celebration event.
- Correcting Reservation Date: Customer corrects a mistaken calendar date due to personal scheduling errors (e.g., 'Wait, I made a mistake! I meant next Saturday the 12th').
- Decreasing Guest Count: Customer requests to reduce the party size because one or more guests cannot attend (e.g., 'drop us down to five', 'can you adjust it to five?').
- Disputing Restaurant Policy: Customer objects to or argues against restaurant dining policies (e.g., mandatory prix fixe set menus or group minimums).
- Dropping Pets and Bags Request: Customer relinquishes a request to bring luggage or pets after learning venue health/pet policies.
- Ending Call to Call Back: Customer concludes the conversation stating they will call back after reaching consensus with group members.
- Ending Request & Asking for Email: Customer drops the active booking attempt and asks for an email address to coordinate future events.
- Explaining Luggage and Pets: Customer explains non-standard space requirements involving personal travel suitcases, luggage, or non-service animals.
- Giving Confused Date Info: Customer demonstrates confusion regarding calendar dates, weekdays, or relative days (e.g., thinking Monday is tomorrow on a Thursday).
- Giving Date, Time & Headcount: Customer provides date, dining time, and guest count together in a single statement (e.g., 'Let’s do 7:15 PM tonight. Just two people').
- Increasing Guest Count: Customer requests to expand party size because additional guests are joining (e.g., 'Can we make that a table for six instead?').
- Initial Table Booking: Customer initiates a new table reservation inquiry (e.g., 'Hi, I’d like to book a table for four', 'Can I get a table reserved for two tomorrow?').
- Inquiring About Halal Food: Customer asks whether meats served comply with Halal dietary certification.
- Inquiring About Vegan Menu: Customer asks whether substantive vegan entrées are offered rather than basic side salads.
- Inquiring About Weekend Table: Customer broadly inquires about table availability across an undefined weekend period without specifying day or time.
- Inquiring About Wheelchair Access: Customer inquires about step-free entry, accessible restrooms, or wheelchair table clearance.
- Making Ambiguous Request: Customer requests a reservation using vague colloquialisms relying on assumed visit history (e.g., 'book me the usual spot and the usual number of people').
- Offering Multiple Times: Customer suggests multiple alternative arrival times due to group schedule conflicts (e.g., 'maybe 5:30 or 6:00 PM. What do you have open?').
- Ordering Delivery: Customer calls trying to place a takeaway food delivery order to a home address.
- Pausing the Reservation: Customer asks the assistant to hold off on finalizing the booking while details are coordinated (e.g., 'please don't book anything yet').
- Providing Contact Information: Customer supplies a phone number for the reservation.
- Providing Customer Name: Customer supplies their name to hold the reservation.
- Providing Date: Customer supplies the reservation date or day of the week.
- Providing Guest Count: Customer states the party size in response to a direct headcount question (e.g., 'There will be six of us').
- Providing Invalid Date: Customer requests a calendar date that does not exist (e.g., February 30th or February 31st).
- Providing Name & Contact: Customer provides both customer name and telephone number together in a single turn.
- Providing Name & Phone: Customer confirms name and telephone number specifically to locate an existing customer account/profile.
- Providing Preferred Time: Customer states the target arrival time (e.g., 'Around 8 PM', 'Let's do 7:00 PM').
- Pushing Reservation Time Back: Customer requests to postpone or delay arrival time due to scheduling delays.
- Reporting Severe Gluten Allergy: Customer inquires about gluten-free food options and verifies strict cookware cross-contamination safety for celiac disease.
- Reporting Severe Peanut Allergy: Customer alerts staff to a severe or airborne peanut allergy and verifies kitchen oil safety.
- Requesting Birthday Note: Customer agrees to or requests a birthday celebration greeting note on the table.
- Requesting Booth & Dietary Info: Customer specifies booth seating while simultaneously confirming absence of dietary restrictions.
- Requesting High Chair & Space: Customer breaks down party demographics (adults + infant) and asks for a high chair or stroller table clearance.
- Requesting Occasion Seating: Customer mentions a special celebration (e.g., anniversary) and requests dedicated seating (e.g., quiet romantic booth away from doors).
- Requesting Patio Seating: Customer requests an outdoor patio dining table.
- Requesting Unrealistic Guest Count: Customer requests an extreme party size (e.g., 60+ people) for immediate same-day dining.
- Requesting Unreasonable Table Setup: Customer demands disruptive or physically impossible table layouts (e.g., pushing 10-12 tables together across a dining room).
- Requesting Work Booth & Outlet: Customer requests a quiet solo table near an electrical wall outlet to charge a laptop.
- Selecting Specific Time: Customer picks a specific dining time slot from options offered by the restaurant.
- Switching to Table Booking: Customer converts an initial inquiry (e.g., delivery call) into an in-person table reservation.

Decision Rules & Disambiguation Guidelines:

1. Handling Overlapping & Confusing Intent Pairs:
   - Providing Name & Contact vs Providing Name & Phone:
     * Use 'Providing Name & Phone' ONLY when the customer provides their name and number explicitly to retrieve an existing profile or history (e.g., 'Mark Rinaldi, phone is 555-011-2390' following 'the usual').
     * For all standard instances of providing both name and phone together, classify as 'Providing Name & Contact'.
   - Changing Guest Count vs Increasing / Decreasing Guest Count:
     * If the customer explicitly asks to expand party size (e.g., 'make that six instead', 'add two people'), classify as 'Increasing Guest Count'.
     * If the customer explicitly asks to reduce party size (e.g., 'drop us down to five', 'one bailed so make it four'), classify as 'Decreasing Guest Count'.
     * If the customer states a correction to a miscount without explicit expand/drop verbs (e.g., 'actually seven, not six'), classify as 'Changing Guest Count'.
   - Accepting Alternative Time vs Accepting Adjusted Time:
     * Use 'Accepting Alternative Time' when the customer accepts an alternative slot offered because their original choice was fully booked (e.g., 'Yes, 8:30 is fine').
     * Use 'Accepting Adjusted Time' when the customer requested to delay/postpone their booking and accepts the new slot (e.g., '1:45 PM is perfect! That gives us breathing room').
   - Providing Preferred Time vs Selecting Specific Time vs Booking with Vague Time:
     * If the time contains imprecise qualifiers ('around 8-ish', '7:30ish', 'sometime after 8'), classify as 'Booking with Vague Time'.
     * If the customer selects a time from options presented by the assistant, classify as 'Selecting Specific Time'.
     * Otherwise, direct statements of preferred dining times belong to 'Providing Preferred Time'.
   - Generic Affirmations ('Yes', 'Okay'):
     * If agreeing to a birthday note offer, classify as 'Requesting Birthday Note'.
     * If agreeing to let the assistant check availability, classify as 'Acknowledging Table Check'.
     * If confirming final reservation details, classify as 'Confirming Booking Details'.

2. Handling Multiple Intents in One Message (Composite Turns):
   - Prioritize composite categories specifically designed to capture multi-slot turns:
     * Date correction + celebration occasion -> 'Correcting Date & Stating Occasion'
     * Seating preference + allergy negative confirmation -> 'Requesting Booth & Dietary Info'
     * Headcount breakdown + high chair / stroller request -> 'Requesting High Chair & Space'
     * Headcount clarification + power outlet / work booth -> 'Requesting Work Booth & Outlet'
     * Date + time + guest count together -> 'Giving Date, Time & Headcount'
     * Customer name + telephone number together -> 'Providing Name & Contact'
   - If a customer combines agreement with a reservation modification (e.g., 'Yes, please. And actually, there will be seven people, not six'), classify according to the operational modification ('Changing Guest Count').

3. Handling Ambiguous, Vague, or Indecisive Requests:
   - If the customer asks for 'the usual spot' or 'usual number of people' relying on past visits, classify as 'Making Ambiguous Request'.
   - If the customer asks for a table over an indefinite weekend timeframe without day or time ('sometime this weekend'), classify as 'Inquiring About Weekend Table'.
   - If the customer asks to hold a floating or undecided party size range ('table that seats anywhere from 8 to 12'), classify as 'Asking for Flexible Seating'.

4. Handling Invalid Dates, Invalid Guest Numbers, & Absurd Requests:
   - If a customer requests a date that does not exist on the calendar (e.g., 'February 30th', 'February 31st'), classify as 'Providing Invalid Date', overriding general booking phrasing.
   - If a customer demonstrates weekday vs relative day confusion (e.g., 'next Monday, which is tomorrow'), classify as 'Giving Confused Date Info'.
   - If a customer requests a table for 'zero people' (to store luggage or pets), classify as 'Asking for Zero-Guest Table'.
   - If a customer requests a massive party size (e.g., 60 or 100 people) for same-day peak dining, classify as 'Requesting Unrealistic Guest Count'.
   - If a customer demands physically disruptive room arrangements (e.g., pushing 10-12 tables together across the dining room), classify as 'Requesting Unreasonable Table Setup'.

5. Handling Unrelated / Out-of-Scope Questions:
   - If the customer asks about parking facilities, lots, or valet, classify as 'Asking About Parking'.
   - If the customer asks for Wi-Fi passwords, classify as 'Asking for Wi-Fi Password'.
   - If the customer attempts to order food delivery to a residential address, classify as 'Ordering Delivery'.

6. Handling Incomplete Sentences, Slang, & Spelling Mistakes:
   - Normalize typos, missing vowels, and grammatical errors to their intended meaning before classifying (e.g., 'tmrw evning' -> tomorrow evening, 'chnage' -> change, 'cancle' -> cancel).
   - Map colloquial terms to their underlying formal concept ('heads' -> guests, 'bailed' -> dropped out, 'yo' -> greeting).
   - For standalone short fragments:
     * 'Table for 2' as an opening inquiry -> 'Initial Table Booking'
     * 'Just two of us' as a party size response -> 'Providing Guest Count'
     * Isolated phone digits (e.g., '9876543210') -> 'Providing Contact Information'
     * 'Under Mark' -> 'Providing Customer Name'

Output Constraints:
1. Return exactly one intent from the allowed list.
2. Return strictly valid JSON only.
3. Do not include explanations, notes, markdown formatting outside JSON, or additional text.
4. Output format:
{
  "intent": "intent_name"
}
"""

# ---------------------------------------------------------------------------
# Classification & Validation Logic
# ---------------------------------------------------------------------------
def classify_intent(message: str) -> dict:
    # 1. Resolve API Key & Provider configuration
    groq_key = os.environ.get("GROQ_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")

    if groq_key:
        api_key = groq_key
        base_url = "https://api.groq.com/openai/v1"
        preferred_model = os.environ.get("LLM_MODEL", "openai/gpt-oss-20b")
        models_to_try = [preferred_model, "groq/compound", "qwen/qwen3.6-27b"]
    elif openai_key and openai_key.startswith("gsk_"):
        api_key = openai_key
        base_url = "https://api.groq.com/openai/v1"
        preferred_model = os.environ.get("LLM_MODEL", "openai/gpt-oss-20b")
        models_to_try = [preferred_model, "groq/compound", "qwen/qwen3.6-27b"]
    elif openai_key and os.environ.get("PROVIDER", "").lower() == "openai":
        api_key = openai_key
        base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        models_to_try = [os.environ.get("LLM_MODEL", "gpt-4o-mini")]
    else:
        return {
            "error": "GROQ_API_KEY is not set. Please set your Groq key before running:\n"
                     "  In PowerShell: $env:GROQ_API_KEY = 'gsk_your_key_here'\n"
                     "  Or create a .env file with: GROQ_API_KEY=gsk_your_key_here"
        }

    # Deduplicate while preserving order
    seen = set()
    models_to_try = [m for m in models_to_try if m and not (m in seen or seen.add(m))]

    last_error = None
    raw_content = None

    # 2. Send request to LLM API (with automatic fallback if model not found)
    for model in models_to_try:
        try:
            response = requests.post(
                f"{base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": f"Customer message:\n\n{message}"}
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.0
                },
                timeout=30
            )
        except requests.exceptions.RequestException as err:
            return {"error": f"API request failed: Connection error ({err})"}

        if response.status_code == 200:
            try:
                result_data = response.json()
                raw_content = result_data["choices"][0]["message"]["content"]
                break
            except (KeyError, IndexError, json.JSONDecodeError) as err:
                last_error = f"Invalid response structure from API: {err}"
                continue
        else:
            try:
                err_json = response.json()
                err_msg = err_json.get("error", {}).get("message", response.text)
            except Exception:
                err_msg = response.text
            last_error = f"API error ({response.status_code}): {err_msg}"
            if response.status_code == 404:
                # Model not found on this endpoint, try next candidate
                continue
            else:
                return {"error": last_error}

    if raw_content is None:
        return {"error": last_error or "No valid model response received."}

    # 5. Parse JSON response using Python's json module
    try:
        data = json.loads(raw_content)
    except json.JSONDecodeError:
        return {"error": "Failed to parse LLM response as JSON."}

    # 6. Validate that the 'intent' field exists
    if not isinstance(data, dict) or "intent" not in data:
        return {"error": "Missing 'intent' field in LLM response."}

    intent = data["intent"]

    # 7. Validate that the returned intent belongs to the allowed list
    if intent not in ALLOWED_INTENTS:
        return {"error": f"Invalid intent returned by model: '{intent}'"}

    return {"intent": intent}

# ---------------------------------------------------------------------------
# Main CLI Entrypoint: Strictly Output Machine-Readable JSON
# ---------------------------------------------------------------------------
def main():
    try:
        customer_message = input().strip()
    except (KeyboardInterrupt, EOFError):
        return

    if not customer_message:
        print(json.dumps({"error": "Customer message cannot be empty."}))
        sys.exit(1)

    result = classify_intent(customer_message)
    print(json.dumps(result))

if __name__ == "__main__":
    main()
