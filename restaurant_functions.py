"""
Restaurant Booking Functions for Function Calling System.

This module provides four standalone functions for restaurant operations:
1. check_availability: Checks whether a table is available for a given date, time, and party size.
2. create_booking: Creates a new table reservation and returns a booking confirmation.
3. modify_booking: Updates an existing reservation's date, time, or party size.
4. cancel_booking: Cancels an existing reservation using the booking ID.

Canonical rule:
`party_size` is the only field used for the number of guests.
For modifications, `new_party_size` is used.
`number_of_guests` is strictly forbidden across all inputs and outputs.
"""

from typing import Optional, Dict, Any


def check_availability(
    date: str,
    time: str,
    party_size: int
) -> Dict[str, Any]:
    """
    Check whether a table is available for the given party size, date, and time.

    Args:
        date: Requested date in YYYY-MM-DD format (or string).
        time: Requested reservation time in HH:MM format (or string).
        party_size: Total number of dining guests as an integer.

    Returns:
        Structured result indicating availability and received parameters.
    """
    try:
        party_size = int(party_size)
    except (ValueError, TypeError):
        pass

    return {
        "success": True,
        "action": "check_availability",
        "date": date,
        "time": time,
        "party_size": party_size,
        "available": True,
        "message": f"Table for {party_size} is available on {date} at {time}."
    }


def create_booking(
    customer_name: str,
    date: str,
    time: str,
    party_size: int
) -> Dict[str, Any]:
    """
    Create a new table reservation for a customer.

    Args:
        customer_name: Name of the customer making the reservation.
        date: Reservation date in YYYY-MM-DD format (or string).
        time: Reservation time in HH:MM format (or string).
        party_size: Total number of dining guests as an integer.

    Returns:
        Structured result with a booking ID and confirmation details.
    """
    try:
        party_size = int(party_size)
    except (ValueError, TypeError):
        pass

    booking_id = f"BK-{abs(hash((customer_name, date, time, party_size))) % 9000 + 1000}"

    return {
        "success": True,
        "action": "create_booking",
        "booking_id": booking_id,
        "customer_name": customer_name,
        "date": date,
        "time": time,
        "party_size": party_size,
        "message": f"Booking confirmed for {customer_name} (Party of {party_size}) on {date} at {time}. Booking ID: {booking_id}."
    }


def modify_booking(
    booking_id: str,
    new_date: Optional[str] = None,
    new_time: Optional[str] = None,
    new_party_size: Optional[int] = None
) -> Dict[str, Any]:
    """
    Modify an existing booking's date, time, or party size.

    Args:
        booking_id: The ID of the existing reservation to modify.
        new_date: Updated reservation date in YYYY-MM-DD format (optional).
        new_time: Updated reservation time in HH:MM format (optional).
        new_party_size: Updated guest count as an integer (optional).

    Returns:
        Structured result with updated booking details.
    """
    if new_party_size is not None:
        try:
            new_party_size = int(new_party_size)
        except (ValueError, TypeError):
            pass

    res = {
        "success": True,
        "action": "modify_booking",
        "booking_id": booking_id,
        "new_date": new_date,
        "new_time": new_time,
        "message": f"Booking {booking_id} successfully updated with new details."
    }
    if new_party_size is not None:
        res["new_party_size"] = new_party_size
    return res


def cancel_booking(booking_id: str) -> Dict[str, Any]:
    """
    Cancel an existing booking using its booking ID.

    Args:
        booking_id: The ID of the reservation to cancel.

    Returns:
        Structured result confirming the cancellation.
    """
    return {
        "success": True,
        "action": "cancel_booking",
        "booking_id": booking_id,
        "message": f"Booking {booking_id} has been successfully cancelled."
    }


# ---------------------------------------------------------------------------
# OpenAI / Groq Compatible Tool / Function Schemas
# ---------------------------------------------------------------------------
RESTAURANT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": "Check whether a restaurant table is available for a specified date, time, and party size. Use this when the customer asks if a table is free or inquires about availability.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "The date for the reservation in ISO 'YYYY-MM-DD' format (e.g., '2026-09-25')."
                    },
                    "time": {
                        "type": "string",
                        "description": "The requested reservation time standardized strictly in 24-hour 'HH:MM' format (e.g., '20:00', '19:30', '13:00')."
                    },
                    "party_size": {
                        "type": "integer",
                        "description": "Total number of dining guests as an integer. Always use 'party_size'. Never use 'number_of_guests'."
                    }
                },
                "required": ["date", "time", "party_size"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_booking",
            "description": "Create and confirm a new restaurant reservation for a customer. Use this when the customer explicitly asks to book a table and provides their name and reservation parameters.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {
                        "type": "string",
                        "description": "The full name of the customer making the reservation (e.g., 'David Miller', 'Sarah Jenkins')."
                    },
                    "date": {
                        "type": "string",
                        "description": "The reservation date in ISO 'YYYY-MM-DD' format (e.g., '2026-09-26')."
                    },
                    "time": {
                        "type": "string",
                        "description": "The requested reservation time standardized strictly in 24-hour 'HH:MM' format (e.g., '20:00', '19:30', '13:00')."
                    },
                    "party_size": {
                        "type": "integer",
                        "description": "Total number of dining guests as an integer. Always use 'party_size'. Never use 'number_of_guests'."
                    }
                },
                "required": ["customer_name", "date", "time", "party_size"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "modify_booking",
            "description": "Modify an existing restaurant booking such as changing the guest count, date, or time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "booking_id": {
                        "type": "string",
                        "description": "The unique reference or ID of the existing booking to modify (e.g., 'BK-2041', 'BK-4092', 'ABC789')."
                    },
                    "new_date": {
                        "type": "string",
                        "description": "The updated date for the reservation in ISO 'YYYY-MM-DD' format (e.g., '2026-09-27')."
                    },
                    "new_time": {
                        "type": "string",
                        "description": "The updated reservation time strictly in 24-hour 'HH:MM' format (e.g., '20:30', '21:00')."
                    },
                    "new_party_size": {
                        "type": "integer",
                        "description": "The updated number of dining guests as an integer. Always use 'new_party_size'. Never use 'new_number_of_guests'."
                    }
                },
                "required": ["booking_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_booking",
            "description": "Cancel an existing restaurant booking using the booking ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "booking_id": {
                        "type": "string",
                        "description": "The unique reference or ID of the booking to cancel (e.g., 'BK-8812', 'BK-5521')."
                    }
                },
                "required": ["booking_id"]
            }
        }
    }
]
