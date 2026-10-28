-- Install independent, parent-cascading Chatwoot integration state.
CREATE TABLE support_chatwoot.threads (
    conversation_id uuid PRIMARY KEY REFERENCES support_app.conversations(id) ON DELETE CASCADE,
    account_id bigint NOT NULL CHECK (account_id>0),
    inbox_id bigint NOT NULL CHECK (inbox_id>0),
    external_id bigint NOT NULL CHECK (external_id>0),
    owner_id uuid NOT NULL,
    human_seen boolean NOT NULL DEFAULT false,
    observed_pause_id uuid,
    next_scan_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(account_id,inbox_id,external_id)
);
CREATE TABLE support_chatwoot.events (
    conversation_id uuid NOT NULL REFERENCES support_chatwoot.threads(conversation_id) ON DELETE CASCADE,
    event_key text NOT NULL CHECK (length(event_key)<=80),
    message_id bigint,
    content text CHECK (length(content)<=8000),
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','accepted','ignored')),
    turn_id uuid REFERENCES support_app.turns(id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY(conversation_id,event_key)
);
CREATE TABLE support_chatwoot.outbound (
    id uuid PRIMARY KEY,
    conversation_id uuid NOT NULL REFERENCES support_chatwoot.threads(conversation_id) ON DELETE CASCADE,
    turn_id uuid NOT NULL REFERENCES support_app.turns(id) ON DELETE CASCADE,
    kind text NOT NULL CHECK (kind IN ('answer','handoff')),
    content text NOT NULL CHECK (length(content)<=10000),
    status text NOT NULL DEFAULT 'ready' CHECK (status IN ('ready','sending','sent','uncertain','suppressed')),
    remote_message_id bigint,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(turn_id,kind)
);
CREATE INDEX chatwoot_event_pending ON support_chatwoot.events(conversation_id,created_at)
    WHERE status='pending';
