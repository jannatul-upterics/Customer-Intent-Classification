"""
Restaurant Booking Functions for Function Calling Prototype.

This module provides four standalone functions for restaurant operations:
1. check_availability: Checks whether a table is available for a given date, time, and party size.
2. create_booking: Creates a new table reservation and returns a booking confirmation.
3. modify_booking: Updates an existing reservation's date, time, or guest count.
4. cancel_booking: Cancels an existing reservation using the booking ID.

Each function returns a simple, structured dictionary showing the action performed
and the arguments received.
"""

from typing import Optional, Dict, Any


def check_availability(
    date: str,
    time: str,
    party_size: Optional[int] = None,
    number_of_guests: Optional[int] = None
) -> Dict[str, Any]:
    """
    Check whether a table is available for the given party size/number of guests, date, and time.

    Args:
        date: Requested date or day (e.g. "Saturday", "tomorrow", "2026-09-12").
        time: Requested reservation time (e.g. "20:00", "8 PM").
        party_size: Total number of dining guests (alias: number_of_guests).
        number_of_guests: Total number of dining guests (alias: party_size).

    Returns:
        Structured result indicating availability and received parameters.
    """
    guests = party_size if party_size is not None else number_of_guests
    try:
        guests = int(guests)
    except (ValueError, TypeError):
        pass

    return {
        "success": True,
        "action": "check_availability",
        "date": date,
        "time": time,
        "party_size": guests,
        "number_of_guests": guests,
        "available": True,
        "message": f"Table for {guests} is available on {date} at {time}."
    }


def create_booking(
    customer_name: str,
    date: str,
    time: str,
    party_size: Optional[int] = None,
    number_of_guests: Optional[int] = None
) -> Dict[str, Any]:
    """
    Create a new table reservation for a customer.

    Args:
        customer_name: Name of the customer making the reservation.
        date: Reservation date or day (e.g. "Saturday", "tomorrow").
        time: Reservation time (e.g. "20:00", "19:30").
        party_size: Total number of dining guests (alias: number_of_guests).
        number_of_guests: Total number of dining guests (alias: party_size).

    Returns:
        Structured result with a booking ID and confirmation details.
    """
    guests = party_size if party_size is not None else number_of_guests
    try:
        guests = int(guests)
    except (ValueError, TypeError):
        pass

    # Generate a simple mock booking ID
    booking_id = f"BK-{abs(hash((customer_name, date, time, guests))) % 9000 + 1000}"

    return {
        "success": True,
        "action": "create_booking",
        "booking_id": booking_id,
        "customer_name": customer_name,
        "date": date,
        "time": time,
        "party_size": guests,
        "number_of_guests": guests,
        "message": f"Booking confirmed for {customer_name} (Party of {guests}) on {date} at {time}. Booking ID: {booking_id}."
    }


def modify_booking(
    booking_id: str,
    new_date: Optional[str] = None,
    new_time: Optional[str] = None,
    new_party_size: Optional[int] = None,
    new_number_of_guests: Optional[int] = None
) -> Dict[str, Any]:
    """
    Modify an existing booking's date, time, or party size.

    Args:
        booking_id: The ID of the existing reservation to modify.
        new_date: Updated reservation date or day (optional).
        new_time: Updated reservation time (optional).
        new_party_size: Updated guest count (alias: new_number_of_guests).
        new_number_of_guests: Updated guest count (alias: new_party_size).

    Returns:
        Structured result with updated booking details.
    """
    new_guests = new_party_size if new_party_size is not None else new_number_of_guests
    if new_guests is not None:
        try:
            new_guests = int(new_guests)
        except (ValueError, TypeError):
            pass

    return {
        "success": True,
        "action": "modify_booking",
        "booking_id": booking_id,
        "new_date": new_date,
        "new_time": new_time,
        "new_party_size": new_guests,
        "new_number_of_guests": new_guests,
        "message": f"Booking {booking_id} successfully updated with new details."
    }


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
                        "description": "The date or day for the reservation (e.g., 'Saturday', 'tomorrow', 'Friday')."
                    },
                    "time": {
                        "type": "string",
                        "description": "The requested reservation time standardized strictly in 24-hour 'HH:MM' format (e.g., '20:00', '19:30', '13:00')."
                    },
                    "party_size": {
                        "type": "integer",
                        "description": "Total number of dining guests as an integer."
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
                        "description": "The full name of the customer making the reservation (e.g., 'Jannatul', 'John Doe')."
                    },
                    "date": {
                        "type": "string",
                        "description": "The reservation date or day (e.g., 'Saturday', 'tomorrow', 'Friday')."
                    },
                    "time": {
                        "type": "string",
                        "description": "The requested reservation time standardized strictly in 24-hour 'HH:MM' format (e.g., '20:00', '19:30', '13:00')."
                    },
                    "party_size": {
                        "type": "integer",
                        "description": "Total number of dining guests as an integer."
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
                        "description": "The unique reference or ID of the existing booking to modify (e.g., 'ABC123', 'BK-1001')."
                    },
                    "new_date": {
                        "type": "string",
                        "description": "The updated date or day for the reservation (e.g., 'Sunday', 'tomorrow')."
                    },
                    "new_time": {
                        "type": "string",
                        "description": "The updated reservation time strictly in 24-hour 'HH:MM' format (e.g., '20:30', '19:00')."
                    },
                    "new_party_size": {
                        "type": "integer",
                        "description": "The updated number of dining guests as an integer."
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
                        "description": "The unique reference or ID of the booking to cancel (e.g., 'ABC123', 'BK-1001')."
                    }
                },
                "required": ["booking_id"]
            }
        }
    }
]

