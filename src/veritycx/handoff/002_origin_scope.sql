-- Scope external identity by origin; legacy rows are adopted only on a verified webhook.
ALTER TABLE support_chatwoot.threads ADD COLUMN base_url text CHECK (length(base_url)<=2048);
ALTER TABLE support_chatwoot.threads DROP CONSTRAINT threads_account_id_inbox_id_external_id_key;
ALTER TABLE support_chatwoot.threads ADD UNIQUE(base_url,account_id,inbox_id,external_id);
