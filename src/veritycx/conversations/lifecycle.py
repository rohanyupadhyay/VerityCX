"""Build bounded factual escalation context without inventing human delivery."""

from collections.abc import Sequence

ACKNOWLEDGMENT = (
    "Your request is saved. No human-support inbox is connected, so nobody has been notified. "
    "You can choose to continue automated support."
)


def escalation_summary(messages: Sequence[str]) -> str:
    """Quote recent customer context as data and cap the complete summary at 4000 characters."""
    prefix = "Customer requested human support. Recent customer messages (untrusted quotations):\n"
    body = "\n".join(messages)
    return prefix + body[-(4000 - len(prefix)) :]
