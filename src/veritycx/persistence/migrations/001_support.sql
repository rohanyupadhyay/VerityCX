-- Establish authoritative support entities; runtime grants are applied by the migration runner.
CREATE TABLE support_app.conversations (
 id uuid PRIMARY KEY, owner_id uuid NOT NULL, schema_version integer NOT NULL DEFAULT 1 CHECK (schema_version = 1),
 revision bigint NOT NULL DEFAULT 1 CHECK (revision > 0), corpus_version text NOT NULL,
 status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','escalation_pending','deleted')),
 customer_count integer NOT NULL DEFAULT 0 CHECK (customer_count BETWEEN 0 AND 100),
 active_job_id uuid, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 activity_at timestamptz NOT NULL DEFAULT clock_timestamp(), expires_at timestamptz NOT NULL,
 deleted_at timestamptz
);
CREATE TABLE support_app.operations (
 owner_id uuid NOT NULL, request_key uuid NOT NULL, kind text NOT NULL CHECK (kind IN ('create','turn','resume','delete')),
 conversation_id uuid NOT NULL REFERENCES support_app.conversations(id),
 request_digest text NOT NULL CHECK (request_digest ~ '^[0-9a-f]{64}$'), resource_id uuid,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(), PRIMARY KEY(owner_id,request_key)
);
CREATE TABLE support_app.turns (
 id uuid PRIMARY KEY, conversation_id uuid NOT NULL REFERENCES support_app.conversations(id),
 sequence integer NOT NULL CHECK (sequence BETWEEN 1 AND 100), request_key uuid NOT NULL,
 text text NOT NULL CHECK (char_length(text) BETWEEN 1 AND 8000),
 status text NOT NULL CHECK (status IN ('accepted','running','completed','failed')), result jsonb,
 processing_started_at timestamptz, deadline_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(), UNIQUE(conversation_id,sequence),
 UNIQUE(conversation_id,request_key),
 CHECK ((processing_started_at IS NULL) = (deadline_at IS NULL)),
 CHECK (deadline_at IS NULL OR deadline_at = processing_started_at + interval '60 seconds')
);
CREATE TABLE support_app.jobs (
 id uuid PRIMARY KEY, conversation_id uuid NOT NULL REFERENCES support_app.conversations(id),
 turn_id uuid REFERENCES support_app.turns(id), kind text NOT NULL CHECK (kind IN ('turn','resume','pause_repair')),
 status text NOT NULL CHECK (status IN ('accepted','running','completed','failed')),
 worker_id uuid, fence bigint NOT NULL DEFAULT 0 CHECK (fence >= 0), lease_until timestamptz,
 checkpoint_id text, checkpoint_ns text NOT NULL DEFAULT '',
 failure_code text CHECK (failure_code IN ('control_failed','incompatible_state')),
 recovery text CHECK (recovery IN ('retry_with_new_pause','operator_required')),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE UNIQUE INDEX one_active_job ON support_app.jobs(conversation_id) WHERE status IN ('accepted','running');
ALTER TABLE support_app.conversations ADD CONSTRAINT active_job_fk FOREIGN KEY(active_job_id)
 REFERENCES support_app.jobs(id) DEFERRABLE INITIALLY DEFERRED;
CREATE INDEX claim_jobs ON support_app.jobs(status,lease_until,created_at);
CREATE TABLE support_app.attempts (
 turn_id uuid NOT NULL REFERENCES support_app.turns(id), ordinal integer NOT NULL CHECK(ordinal BETWEEN 1 AND 2),
 status text NOT NULL CHECK(status IN ('reserved','succeeded','failed')), request_digest text NOT NULL,
 result_json text, failure_category text, started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 ended_at timestamptz, PRIMARY KEY(turn_id,ordinal)
);
CREATE TABLE support_app.escalations (
 id uuid PRIMARY KEY, conversation_id uuid NOT NULL REFERENCES support_app.conversations(id),
 triggering_turn_id uuid NOT NULL REFERENCES support_app.turns(id), reason text NOT NULL,
 summary text NOT NULL CHECK(char_length(summary) <= 4000), source_ids jsonb NOT NULL DEFAULT '[]',
 pause_id uuid NOT NULL UNIQUE, status text NOT NULL CHECK(status IN ('pending','cancelled')),
 consumed_operation_id uuid, created_at timestamptz NOT NULL DEFAULT clock_timestamp(), consumed_at timestamptz
);
CREATE UNIQUE INDEX one_pending_pause ON support_app.escalations(conversation_id) WHERE status='pending';
CREATE TABLE support_app.audit (
 id uuid PRIMARY KEY, conversation_id uuid NOT NULL REFERENCES support_app.conversations(id),
 turn_id uuid NOT NULL REFERENCES support_app.turns(id), correlation_id uuid NOT NULL,
 stage text NOT NULL, outcome text NOT NULL, route text NOT NULL, source_ids jsonb NOT NULL DEFAULT '[]',
 elapsed_ms bigint NOT NULL DEFAULT 0 CHECK(elapsed_ms >= 0), failure_category text, model text,
 input_tokens bigint CHECK(input_tokens >= 0), output_tokens bigint CHECK(output_tokens >= 0)
);
CREATE TABLE support_app.worker_heartbeats (worker_id uuid PRIMARY KEY, last_seen timestamptz NOT NULL);
CREATE INDEX retention_candidates ON support_app.conversations(expires_at);
