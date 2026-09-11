"""
Restaurant Actions Module.

Provides four beginner-friendly functions for restaurant operations:
1. check_availability: Check if a table is free for given date, time, and guest count.
2. create_booking: Create a new reservation and return a booking confirmation.
3. modify_booking: Modify an existing reservation (guests, date, time).
4. cancel_booking: Cancel an existing reservation by booking ID.
"""

from typing import Optional, Dict, Any
import random


def check_availability(
    date: str,
    time: str,
    number_of_guests: int
) -> Dict[str, Any]:
    """
    Check whether a table is available for a specified date, time, and party size.

    Input Parameters:
        date (str): Requested booking date or day (e.g., '2026-09-12', 'Saturday', 'tomorrow').
        time (str): Requested booking time (e.g., '20:00', '7:30 PM').
        number_of_guests (int): Number of guests dining.

    Expected Output:
        dict: A structured dictionary indicating availability status and request details.
    """
    # Simple input validation
    try:
        guests = int(number_of_guests)
        if guests <= 0:
            return {
                "status": "error",
                "action": "check_availability",
                "error": "number_of_guests must be a positive integer."
            }
    except (ValueError, TypeError):
        return {
            "status": "error",
            "action": "check_availability",
            "error": f"Invalid number_of_guests value: {number_of_guests}"
        }

    return {
        "status": "success",
        "action": "check_availability",
        "available": True,
        "date": str(date).strip(),
        "time": str(time).strip(),
        "number_of_guests": guests,
        "message": f"A table for {guests} guests is available on {date} at {time}."
    }


def create_booking(
    customer_name: str,
    date: str,
    time: str,
    number_of_guests: int
) -> Dict[str, Any]:
    """
    Create a new restaurant booking for a customer.

    Input Parameters:
        customer_name (str): Full name of the customer making the reservation.
        date (str): Date of the reservation (e.g., '2026-09-12', 'Saturday').
        time (str): Time of the reservation (e.g., '20:00', '19:30').
        number_of_guests (int): Total number of guests dining.

    Expected Output:
        dict: Confirmation details including a generated booking ID.
    """
    if not customer_name or not str(customer_name).strip():
        return {
            "status": "error",
            "action": "create_booking",
            "error": "customer_name is required."
        }

    try:
        guests = int(number_of_guests)
        if guests <= 0:
            return {
                "status": "error",
                "action": "create_booking",
                "error": "number_of_guests must be greater than zero."
            }
    except (ValueError, TypeError):
        return {
            "status": "error",
            "action": "create_booking",
            "error": f"Invalid number_of_guests value: {number_of_guests}"
        }

    # Generate a readable mock booking ID (e.g. RES-1042)
    booking_id = f"RES-{random.randint(1000, 9999)}"

    return {
        "status": "success",
        "action": "create_booking",
        "booking_id": booking_id,
        "customer_name": str(customer_name).strip(),
        "date": str(date).strip(),
        "time": str(time).strip(),
        "number_of_guests": guests,
        "message": f"Booking confirmed for {customer_name} ({guests} guests) on {date} at {time}. Booking ID: {booking_id}."
    }


def modify_booking(
    booking_id: str,
    new_date: Optional[str] = None,
    new_time: Optional[str] = None,
    new_number_of_guests: Optional[int] = None
) -> Dict[str, Any]:
    """
    Modify an existing booking's date, time, or guest count.

    Input Parameters:
        booking_id (str): Unique identifier of the reservation to modify.
        new_date (str, optional): New booking date or day.
        new_time (str, optional): New booking time.
        new_number_of_guests (int, optional): Updated guest count.

    Expected Output:
        dict: Summary of updated fields and confirmation message.
    """
    if not booking_id or not str(booking_id).strip():
        return {
            "status": "error",
            "action": "modify_booking",
            "error": "booking_id is required."
        }

    updated_fields = {}

    if new_date is not None:
        updated_fields["date"] = str(new_date).strip()

    if new_time is not None:
        updated_fields["time"] = str(new_time).strip()

    if new_number_of_guests is not None:
        try:
            guests = int(new_number_of_guests)
            if guests > 0:
                updated_fields["number_of_guests"] = guests
            else:
                return {
                    "status": "error",
                    "action": "modify_booking",
                    "error": "new_number_of_guests must be greater than zero."
                }
        except (ValueError, TypeError):
            return {
                "status": "error",
                "action": "modify_booking",
                "error": f"Invalid new_number_of_guests: {new_number_of_guests}"
            }

    if not updated_fields:
        return {
            "status": "error",
            "action": "modify_booking",
            "error": "At least one field (new_date, new_time, or new_number_of_guests) must be provided to modify."
        }

    return {
        "status": "success",
        "action": "modify_booking",
        "booking_id": str(booking_id).strip(),
        "updated_fields": updated_fields,
        "message": f"Booking {booking_id} successfully updated with: {updated_fields}."
    }


def cancel_booking(
    booking_id: str
) -> Dict[str, Any]:
    """
    Cancel an existing booking using its booking ID.

    Input Parameters:
        booking_id (str): Unique identifier of the reservation to cancel.

    Expected Output:
        dict: Confirmation of the cancellation.
    """
    if not booking_id or not str(booking_id).strip():
        return {
            "status": "error",
            "action": "cancel_booking",
            "error": "booking_id is required."
        }

    return {
        "status": "success",
        "action": "cancel_booking",
        "booking_id": str(booking_id).strip(),
        "message": f"Booking {booking_id} has been successfully cancelled."
    }
