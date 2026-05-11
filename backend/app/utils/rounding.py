"""Rounding helpers for invoice totals."""

ROUND_TO_FIVE_RUPEES_STEP_PAISE = 500


def round_paise_to_nearest_5(value: int | float | None) -> int:
    """Round down to the nearest 0/5 rupees (business rule)."""
    if value is None:
        return 0
    normalized = int(round(float(value)))
    if normalized >= 0:
        return (normalized // ROUND_TO_FIVE_RUPEES_STEP_PAISE) * ROUND_TO_FIVE_RUPEES_STEP_PAISE
    return -((-normalized) // ROUND_TO_FIVE_RUPEES_STEP_PAISE) * ROUND_TO_FIVE_RUPEES_STEP_PAISE
