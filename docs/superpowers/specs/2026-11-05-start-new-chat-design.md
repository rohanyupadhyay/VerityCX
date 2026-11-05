# Start a fresh customer chat

## Intent

Every page action that starts a conversation should open a fresh VerityCX chat.
The customer does not need access to previous chats for now. Existing server
records must remain preserved.

## Approaches

- **Reset the browser session using Chatwoot's supported SDK:** selected by the
  user's request to start fresh without remembering old chats. This creates a
  new anonymous session without deleting or resolving previous conversations.
- **Keep a conversation history and let customers select threads:** more work
  and unnecessary for the requested behavior.
- **Enable customer-side conversation resolution:** conflicts with the existing
  human-handoff protection, so it is unsuitable for this change.

## Behavior

- All page chat entry points, including “Start a conversation,” start a fresh
  session using the native Chatwoot widget. The floating widget bubble continues
  to reopen the current conversation.
- While starting a session, disable page chat entry points and report
  “Starting a new chat.” Repeated clicks must not initiate overlapping resets.
- Open the fresh widget only after the reset session reports readiness. In the
  pinned Chatwoot version, reset suppresses the usual `chatwoot:ready` event;
  accept its widget-loaded message only from the configured origin and actual
  widget iframe, with a new session token so earlier sessions cannot finish a
  later reset. Track observed tokens only in memory, without logging or persisting
  them. Bound waiting to 15 seconds.
- On reset failure or timeout, show the existing unavailable state and retry
  action. Dispose listeners and timers on unmount; ignore stale events.
- Do not send a message automatically, delete stored conversations, or alter
  human ownership or customer-side conversation resolution settings.

## Scope and validation

This is a small frontend change using the existing React/TypeScript connection
wrapper, with no new dependencies, database migration, or backend endpoint.
Add regression coverage for a fresh session, repeated clicks, genuine versus
unrelated readiness events, timeout, reset exceptions, and unmount cleanup.
Run the frontend suite, type checking, formatting checks, and production build,
then check the actual local Chatwoot widget in the browser without calling the
model provider.
