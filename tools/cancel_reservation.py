"""
Tool: Cancel Reservation
"""

from utils.database import load_reservations, save_reservations


def execute(reservation_id=None, phone=None, phone_or_id=None):
    """Cancel reservation.

    Supports cancel by confirmation id (`reservation_id`), by `phone`, or by
    `phone_or_id` (generic). Returns an object with cancellation status or an
    error. Backwards-compatible with the previous single-arg signature.
    """
    try:
        reservations = load_reservations()

        # Determine lookup key
        target = None
        if reservation_id:
            target = reservation_id
        elif phone_or_id:
            target = phone_or_id
        elif phone:
            target = phone

        if not target:
            return {"error": "No reservation_id or phone provided"}

        # Find by confirmation_id first, then by phone
        reservation = next(
            (r for r in reservations if r.get("confirmation_id") == target),
            None
        )

        if reservation is None:
            reservation = next(
                (r for r in reservations if r.get("phone") == target),
                None
            )

        if not reservation:
            return {"reservation": None, "error": "Reservation not found"}

        reservation["status"] = "cancelled"
        save_reservations(reservations)

        return {
            "confirmation_id": reservation.get("confirmation_id"),
            "status": "cancelled",
            "reservation": reservation,
        }

    except Exception as e:
        return {"error": f"Cancellation failed: {str(e)}"}
