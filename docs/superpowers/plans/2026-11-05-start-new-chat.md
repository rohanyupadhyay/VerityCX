# Start New Chat Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Make page conversation actions start a fresh customer chat.

**Architecture:** Keep the native Chatwoot widget and reset its anonymous browser
session through the supported SDK. The connection wrapper owns reset readiness,
timeout, duplicate-click protection, and cleanup; React renders the starting state.

**Tech Stack:** React, TypeScript, Chatwoot v4.19.1, Vitest/jsdom.

**Spec:** [Approved design](../specs/2026-11-05-start-new-chat-design.md).

## Global Constraints

- Existing server records must remain preserved.
- No new dependencies, database migration, or backend endpoint.
- Do not send a message automatically or alter human ownership or customer-side conversation resolution settings.
- Bound waiting to 15 seconds.
- The floating widget bubble continues to reopen the current conversation.

## Review Focus

- Repeated clicks during reset must not reset or reopen an old session.
- Readiness from another origin, window, or old readiness event must not finish reset.
- Malformed messages must not throw or expose upstream data.
- Timeout, SDK exceptions, and disposal must remove reset listeners.
- Both home and bank pages must show the starting state and disable launchers.

### Task 1: Fresh session lifecycle and page integration

**Files:** Modify `frontend/src/chat.ts`, `frontend/src/App.tsx`,
`frontend/src/BankPages.tsx`; test `frontend/tests/chat.test.ts`,
`frontend/tests/App.test.tsx`, and `frontend/tests/BankPages.test.tsx`.

**Interfaces:** Consumes the existing public Chatwoot configuration and SDK.
Produces `ChatConnection.startNew(): boolean` and the `starting` ChatState;
retains `open(): boolean` for reopening an already-ready widget.

- [x] Write failing lifecycle tests: real wrapper with simulated external SDK,
  actual iframe MessageEvent source/origin, success, invalid readiness, repeated
  clicks, timeout, thrown reset, missing reset/iframe, and disposal.
- [x] Run `npm test -- frontend/tests/chat.test.ts`; observe failures because
  `startNew` is absent.
- [x] Implement reset through SDK, a scoped trusted widget-loaded listener,
  bounded waiting, cleanup, and automatic opening after readiness.
- [x] Update page tests to expect disabled entry points and starting copy during
  reset, then ready controls after trusted readiness; cover bank page copy too.
- [x] Run the page tests; observe failures before wiring the new behavior.
- [x] Wire page chat actions to `startNew`, render starting copy on home and
  bank pages, preserving normal native-bubble behavior.
- [x] Run `npm test`, `npm run format:check`, and `npm run build`.
  Expected: all frontend tests, formatting, type checking, and build pass.
- [x] Refresh the local browser and verify resetting removes old history and
  opens a fresh native widget; send no messages or model requests.
- [x] Obtain one fresh review, address material findings, and leave changes on
  the feature branch for review. Commit/push/merge require the user's request.
