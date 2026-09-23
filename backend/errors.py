def is_billing_error(error: Exception) -> bool:
    """Identify provider failures caused by an exhausted or unavailable balance."""
    status = getattr(error, "status_code", getattr(error, "status", None))
    message = str(error).lower()
    mentions_billing = any(term in message for term in ("credit balance", "insufficient credits", "billing"))
    return status == 402 or mentions_billing
