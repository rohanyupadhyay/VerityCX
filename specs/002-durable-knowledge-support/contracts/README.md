<!-- Maps the Feature 002 public and internal design contracts and their verification responsibilities. -->

# Durable Support Contracts

These documents define interfaces to implement for Feature 002. They are not running APIs.

- [HTTP API](http-api.md): authorization, payloads, polling, idempotency and errors.
- [Execution](execution.md): worker/checkpoint transactions, budgets, interrupts and deletion.
- [Knowledge and provider](knowledge-provider.md): permitted corpus, retrieval and provider wire values.
- [Configuration](configuration.md): nonsecret settings, local credentials, commands and audit export.

The [specification](../spec.md) governs product requirements; the [data model](../data-model.md) governs
entities. Implementation must test observable contracts and document changes in the same change set.
Run `uv run mdformat --check specs/002-durable-knowledge-support/contracts` from the Git root.
Dependencies and setup are in the [quickstart](../quickstart.md). Missing validation, unsupported
schema versions, misleading delivery claims and unsafe retry/ownership behavior are contract failures.
