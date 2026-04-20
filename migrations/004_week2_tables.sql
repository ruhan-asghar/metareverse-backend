-- backend/migrations/004_week2_tables.sql

CREATE TABLE IF NOT EXISTS notifications (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id uuid REFERENCES users(id) ON DELETE CASCADE,
  kind text NOT NULL,
  title text NOT NULL,
  body text,
  data jsonb DEFAULT '{}',
  read_at timestamptz,
  created_at timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS notifications_org_user_created_idx ON notifications(org_id, user_id, created_at DESC);
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS notifications_rls ON notifications;
CREATE POLICY notifications_rls ON notifications
  USING (org_id = current_setting('app.current_org_id', true)::uuid);

CREATE TABLE IF NOT EXISTS dead_letter (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  task_name text NOT NULL,
  args jsonb NOT NULL,
  kwargs jsonb NOT NULL,
  exception text NOT NULL,
  traceback text,
  org_id uuid,
  retries int DEFAULT 0,
  created_at timestamptz DEFAULT now(),
  resolved_at timestamptz
);
CREATE INDEX IF NOT EXISTS dead_letter_created_idx ON dead_letter(created_at DESC);

CREATE TABLE IF NOT EXISTS system_metrics (
  id bigserial PRIMARY KEY,
  recorded_at timestamptz DEFAULT now(),
  queue_depth_publish int,
  queue_depth_insights int,
  queue_depth_email int,
  avg_publish_latency_ms int,
  error_rate_5m numeric(5,4)
);
CREATE INDEX IF NOT EXISTS system_metrics_recorded_idx ON system_metrics(recorded_at DESC);

ALTER TABLE posts ADD COLUMN IF NOT EXISTS reclaim_count int DEFAULT 0;
ALTER TABLE posts ADD COLUMN IF NOT EXISTS publishing_started_at timestamptz;
