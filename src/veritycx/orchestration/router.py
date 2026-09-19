"""Route English intents deterministically without provider calls or operational capabilities."""

import re
from typing import Literal

type Route = Literal["human", "unavailable", "clarify", "knowledge"]
RULE_VERSION = 1


def route_intent(message: str) -> Route:
    """Prioritize explicit human requests, operations and ambiguity before knowledge."""
    text = message.casefold()
    clauses = re.split(r"[;.!?]", text)
    for clause in clauses:
        human = re.search(r"\b(human|agent|representative|someone real|person)\b", clause)
        intent = re.search(
            r"\b(want|need|speak|talk|connect|contact|escalate|please|get)\b", clause
        )
        negated = re.search(r"\b(no|not|never|don't|do not|without)\b", clause)
        if human and intent and not negated:
            return "human"
    if re.search(
        r"\b(transfer (my |the |funds|money)|dispute my|reverse my|close my|"
        r"change my (address|account)|cancel my|pay my)\b",
        text,
    ):
        return "unavailable"
    if re.search(
        r"\b(resume automation|change my owner|ignore (the |all )?instructions|system prompt)\b",
        text,
    ):
        return "clarify"
    if not re.search(r"\b(what|how|when|which|policy|fee|limit|rate|period|explain|tell)\b", text):
        return "clarify"
    return "knowledge"
