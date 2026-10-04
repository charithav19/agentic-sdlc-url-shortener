CREATE TABLE click_events (
  id uuid PRIMARY KEY,
  link_id uuid NOT NULL REFERENCES links(id),
  occurred_at timestamptz NOT NULL,
  referrer varchar(512),
  user_agent_category varchar(16) NOT NULL,
  trace_id varchar(64) NOT NULL,
  CONSTRAINT ck_click_events_user_agent_category
    CHECK (user_agent_category IN ('BOT', 'MOBILE', 'DESKTOP', 'OTHER'))
);

CREATE INDEX ix_click_events_link_occurred_at ON click_events (link_id, occurred_at);
