def is_billing_error(error: Exception) -> bool:
    """Identify provider failures caused by an exhausted or unavailable balance."""
    status = getattr(error, "status_code", getattr(error, "status", None))
    message = str(error).lower()
    return (
        status in {402, 403}
        or "credit balance" in message
        or "insufficient credits" in message
        or ("billing" in message and status in {400, 402, 403})
    )