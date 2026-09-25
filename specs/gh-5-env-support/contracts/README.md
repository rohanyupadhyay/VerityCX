<!-- Indexes the developer-visible environment contracts for this feature. -->

# Environment Contracts

This directory defines the configuration interfaces introduced by Feature GH-5. The
[environment contract](environment.md) governs the root `.env` acquisition boundary, the tracked
`.env.example` name set, and the value-blind drift-check command. It changes no HTTP or database
contract.

Implementation and validation commands are described in the feature [quickstart](../quickstart.md).
