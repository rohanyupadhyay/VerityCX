-- Keep one durably spent rewrite call per turn, separate from answer attempts.
CREATE TABLE support_app.query_rewrites (
 turn_id uuid PRIMARY KEY REFERENCES support_app.turns(id) ON DELETE CASCADE,
 request_digest text NOT NULL,
 model text NOT NULL,
 prompt_version integer NOT NULL CHECK (prompt_version = 1),
 status text NOT NULL CHECK (status IN ('reserved','succeeded','failed')),
 result_json text,
 failure_category text,
 input_tokens bigint CHECK (input_tokens >= 0),
 output_tokens bigint CHECK (output_tokens >= 0),
 started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 ended_at timestamptz,
 selected_source_ids jsonb NOT NULL DEFAULT '[]'
   CHECK (jsonb_typeof(selected_source_ids) = 'array' AND jsonb_array_length(selected_source_ids) <= 6),
 retrieval_mode text CHECK (retrieval_mode IN ('primary','synonym','empty')),
 expanded_term_count integer NOT NULL DEFAULT 0 CHECK (expanded_term_count BETWEEN 0 AND 12),
 CHECK ((status = 'succeeded') = (result_json IS NOT NULL))
);
