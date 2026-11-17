-- Preserve historical rewrite versions while recording the discovery-context prompt.
ALTER TABLE support_app.query_rewrites
 DROP CONSTRAINT query_rewrites_prompt_version_check,
 ADD CONSTRAINT query_rewrites_prompt_version_check CHECK (prompt_version IN (1,2,3));
