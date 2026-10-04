CREATE TABLE links (
  id uuid PRIMARY KEY,
  short_code varchar(7) NOT NULL,
  original_url text NOT NULL,
  status varchar(16) NOT NULL,
  created_at timestamptz NOT NULL,
  expires_at timestamptz,
  version bigint NOT NULL DEFAULT 0,
  CONSTRAINT uk_links_short_code UNIQUE (short_code),
  CONSTRAINT ck_links_code_format CHECK (short_code ~ '^[A-Za-z0-9]{7}$'),
  CONSTRAINT ck_links_status CHECK (status IN ('ACTIVE', 'DISABLED'))
);
