ALTER TABLE links ALTER COLUMN short_code TYPE varchar(32);
ALTER TABLE links DROP CONSTRAINT ck_links_code_format;
ALTER TABLE links ADD CONSTRAINT ck_links_code_format
  CHECK (short_code ~ '^[A-Za-z0-9_-]{3,32}$');

CREATE TABLE idempotency_records (
  id uuid PRIMARY KEY,
  caller_scope varchar(128) NOT NULL,
  request_key varchar(128) NOT NULL,
  request_fingerprint varchar(64) NOT NULL,
  link_id uuid NOT NULL REFERENCES links(id),
  response_json text NOT NULL,
  created_at timestamptz NOT NULL,
  CONSTRAINT uk_idempotency_scope_key UNIQUE (caller_scope, request_key)
);
