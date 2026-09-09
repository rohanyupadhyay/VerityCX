<!-- Preserves the original platform vision as future scope, not implementation status. -->

# VerityCX Platform Vision

The following original vision describes the intended future platform. It is **not a claim of
current implementation**. Feature 001 currently provides data acquisition, validation, and
inspection only; see the [root README](../README.md) and [feature tasks](../specs/001-acquire-tau3-banking/tasks.md)
for implemented scope and remaining acceptance work.

## Original Vision

VerityCX is a production-oriented, stateful multi-agent customer-support platform for banking, built and evaluated using the open-source τ³-Banking benchmark. It routes multi-turn conversations between specialised knowledge, account-operations, payments and dispute-risk agents while maintaining shared typed state and persistent conversation checkpoints.

Responses are grounded in a large collection of interconnected banking product, policy and procedure documents. Customer-specific information is obtained through controlled tools operating on synthetic accounts and transactions. Sensitive or consequential actions require verification, policy checks and appropriate approval, while complex or high-risk cases can be escalated to a human agent without losing conversation context.

The platform combines LangGraph orchestration, FastAPI, PostgreSQL, Docker and LangSmith-based observability with τ³-Banking’s deterministic evaluation environment. It measures task completion, routing accuracy, retrieval quality, policy compliance, reliability, latency, cost and human-handoff behaviour. Additional adversarial tests evaluate prompt injection resistance, sensitive-data handling and prevention of unauthorised actions.
