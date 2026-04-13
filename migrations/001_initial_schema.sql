-- MetaReverse — Initial Schema
-- Run against Supabase PostgreSQL
-- All tables use UUID PKs and timestamps

-- ============================================================
-- EXTENSIONS
-- ============================================================
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- ENUMS
-- ============================================================

CREATE TYPE user_role AS ENUM (
  'owner',
  'co_owner',
  'manager',
  'publisher',
  'approver',
  'analyst'
);

CREATE TYPE platform_type AS ENUM (
  'facebook',
  'instagram',
  'threads'
);

CREATE TYPE post_status AS ENUM (
  'draft',
  'pending_approval',
  'changes_requested',
  'rejected',
  'queued',
  'publishing',
  'published',
  'failed_temporary',
  'failed_needs_editing',
  'reconnect_required',
  'paused'
);

CREATE TYPE media_type AS ENUM (
  'photo',
  'reel',
  'text'
);

CREATE TYPE approval_action AS ENUM (
  'approved',
  'rejected',
  'changes_requested'
);

CREATE TYPE posting_id_status AS ENUM (
  'active',
  'expired',
  'revoked',
  'retired'
);

CREATE TYPE page_status AS ENUM (
  'ready',
  'needs_setup',
  'paused',
  'inactive',
  'token_expired',
  'token_expiring'
);

CREATE TYPE invite_status AS ENUM (
  'pending',
  'accepted',
  'expired',
  'invalidated'
);

CREATE TYPE team_member_status AS ENUM (
  'active',
  'pending',
  'removed'
);

CREATE TYPE failed_category AS ENUM (
  'temporary_issue',
  'reconnect_needed',
  'needs_editing'
);

CREATE TYPE monetization_status AS ENUM (
  'enrolled',
  'not_enrolled',
  'ineligible'
);

CREATE TYPE rotation_mode AS ENUM (
  'round_robin'
);

-- ============================================================
-- TABLES
-- ============================================================

-- 1. Organizations (Clerk org mapping — tenant root)
CREATE TABLE organizations (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  clerk_org_id  TEXT UNIQUE NOT NULL,
  name          TEXT NOT NULL,
  slug          TEXT UNIQUE,
  plan          TEXT NOT NULL DEFAULT 'free',
  storage_used_bytes  BIGINT NOT NULL DEFAULT 0,
  storage_limit_bytes BIGINT NOT NULL DEFAULT 5368709120, -- 5 GB default
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2. Users (synced from Clerk webhooks)
CREATE TABLE users (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  clerk_user_id TEXT UNIQUE NOT NULL,
  org_id        UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  email         TEXT NOT NULL,
  first_name    TEXT,
  last_name     TEXT,
  avatar_url    TEXT,
  is_active     BOOLEAN NOT NULL DEFAULT true,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_users_clerk_id ON users(clerk_user_id);
CREATE INDEX idx_users_org ON users(org_id);

-- 3. Batches (named groups of pages — unit of access control)
CREATE TABLE batches (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id        UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  name          TEXT NOT NULL,
  color         TEXT NOT NULL DEFAULT '#3b82f6',
  description   TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(org_id, name)
);
CREATE INDEX idx_batches_org ON batches(org_id);

-- 4. Pages (Facebook / Instagram / Threads pages)
CREATE TABLE pages (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id                UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  batch_id              UUID NOT NULL REFERENCES batches(id) ON DELETE RESTRICT,
  platform              platform_type NOT NULL,
  platform_page_id      TEXT NOT NULL,
  name                  TEXT NOT NULL,
  avatar_url            TEXT,
  follower_count        INTEGER DEFAULT 0,
  follower_count_updated_at TIMESTAMPTZ,
  timezone              TEXT NOT NULL DEFAULT 'UTC',
  post_interval_hours   INTEGER NOT NULL DEFAULT 4 CHECK (post_interval_hours IN (1, 2, 3, 4, 6, 8)),
  active_hours_start    TIME,
  active_hours_end      TIME,
  require_approval      BOOLEAN NOT NULL DEFAULT false,
  rotation_mode         rotation_mode NOT NULL DEFAULT 'round_robin',
  monetization_status   monetization_status NOT NULL DEFAULT 'not_enrolled',
  status                page_status NOT NULL DEFAULT 'needs_setup',
  encrypted_access_token BYTEA,
  token_expires_at      TIMESTAMPTZ,
  is_active             BOOLEAN NOT NULL DEFAULT true,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(org_id, platform, platform_page_id)
);
CREATE INDEX idx_pages_org ON pages(org_id);
CREATE INDEX idx_pages_batch ON pages(batch_id);
CREATE INDEX idx_pages_status ON pages(status);

-- 5. Posting IDs (Facebook user accounts that make API calls on behalf of pages)
CREATE TABLE posting_ids (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id                UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  facebook_user_id      TEXT NOT NULL,
  name                  TEXT NOT NULL,
  avatar_url            TEXT,
  encrypted_access_token BYTEA,
  token_expires_at      TIMESTAMPTZ,
  status                posting_id_status NOT NULL DEFAULT 'active',
  health_score          INTEGER NOT NULL DEFAULT 100 CHECK (health_score >= 0 AND health_score <= 100),
  reach_28d             BIGINT DEFAULT 0,
  last_used_at          TIMESTAMPTZ,
  retired_at            TIMESTAMPTZ,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(org_id, facebook_user_id)
);
CREATE INDEX idx_posting_ids_org ON posting_ids(org_id);
CREATE INDEX idx_posting_ids_status ON posting_ids(status);

-- 6. Page-PostingID assignments (which posting IDs are assigned to which pages)
CREATE TABLE page_posting_id_assignments (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  page_id       UUID NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
  posting_id_id UUID NOT NULL REFERENCES posting_ids(id) ON DELETE CASCADE,
  sort_order    INTEGER NOT NULL DEFAULT 0,
  last_used_at  TIMESTAMPTZ,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(page_id, posting_id_id)
);
CREATE INDEX idx_ppia_page ON page_posting_id_assignments(page_id);

-- 7. Posts (content items with full state machine)
CREATE TABLE posts (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id                UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  page_id               UUID NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
  created_by            UUID NOT NULL REFERENCES users(id),
  posting_id_used       UUID REFERENCES posting_ids(id),
  status                post_status NOT NULL DEFAULT 'draft',
  failed_category       failed_category,
  media_type            media_type NOT NULL DEFAULT 'photo',
  caption_facebook      TEXT,
  caption_instagram     TEXT,
  caption_threads       TEXT,
  publish_to_facebook   BOOLEAN NOT NULL DEFAULT true,
  publish_to_instagram  BOOLEAN NOT NULL DEFAULT false,
  publish_to_threads    BOOLEAN NOT NULL DEFAULT false,
  scheduled_at          TIMESTAMPTZ,
  published_at          TIMESTAMPTZ,
  failed_at             TIMESTAMPTZ,
  failure_reason        TEXT,
  retry_count           INTEGER NOT NULL DEFAULT 0,
  platform_post_id_fb   TEXT,
  platform_post_id_ig   TEXT,
  platform_post_id_th   TEXT,
  file_hash             TEXT, -- SHA-256 for duplicate detection
  is_outside_active_hours BOOLEAN NOT NULL DEFAULT false,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_posts_org ON posts(org_id);
CREATE INDEX idx_posts_page ON posts(page_id);
CREATE INDEX idx_posts_status ON posts(status);
CREATE INDEX idx_posts_scheduled ON posts(scheduled_at) WHERE status = 'queued';
CREATE INDEX idx_posts_created_by ON posts(created_by);
CREATE INDEX idx_posts_file_hash ON posts(file_hash) WHERE file_hash IS NOT NULL;

-- 8. Post media files
CREATE TABLE post_media (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  post_id       UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
  org_id        UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  file_url      TEXT NOT NULL,
  file_key      TEXT NOT NULL, -- R2 object key
  file_hash     TEXT NOT NULL, -- SHA-256
  file_size     BIGINT NOT NULL,
  mime_type     TEXT NOT NULL,
  width         INTEGER,
  height        INTEGER,
  duration_secs REAL, -- for reels/videos
  sort_order    INTEGER NOT NULL DEFAULT 0,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_post_media_post ON post_media(post_id);
CREATE INDEX idx_post_media_hash ON post_media(file_hash);

-- 9. Thread comments (FB only, up to 3 per post)
CREATE TABLE thread_comments (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  post_id       UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
  content       TEXT NOT NULL,
  sort_order    INTEGER NOT NULL CHECK (sort_order >= 0 AND sort_order <= 2),
  platform_comment_id TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(post_id, sort_order)
);

-- 10. Approvals (review records)
CREATE TABLE approvals (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  post_id       UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
  reviewed_by   UUID NOT NULL REFERENCES users(id),
  action        approval_action NOT NULL,
  comment       TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_approvals_post ON approvals(post_id);
CREATE INDEX idx_approvals_reviewer ON approvals(reviewed_by);

-- 11. Team members (users with stackable roles per batch)
CREATE TABLE team_members (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id        UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  roles         user_role[] NOT NULL DEFAULT '{}',
  batch_ids     UUID[] NOT NULL DEFAULT '{}',
  status        team_member_status NOT NULL DEFAULT 'active',
  invited_by    UUID REFERENCES users(id),
  invited_at    TIMESTAMPTZ,
  joined_at     TIMESTAMPTZ,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(org_id, user_id)
);
CREATE INDEX idx_team_members_org ON team_members(org_id);
CREATE INDEX idx_team_members_user ON team_members(user_id);

-- 12. Invite links (7-day expiry)
CREATE TABLE invite_links (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  token           TEXT UNIQUE NOT NULL DEFAULT encode(gen_random_bytes(32), 'hex'),
  email           TEXT NOT NULL,
  roles           user_role[] NOT NULL,
  batch_ids       UUID[] NOT NULL DEFAULT '{}',
  invited_by      UUID NOT NULL REFERENCES users(id),
  expires_at      TIMESTAMPTZ NOT NULL DEFAULT (now() + INTERVAL '7 days'),
  accepted_at     TIMESTAMPTZ,
  invalidated_at  TIMESTAMPTZ,
  status          invite_status NOT NULL DEFAULT 'pending',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_invite_links_token ON invite_links(token);
CREATE INDEX idx_invite_links_org ON invite_links(org_id);
CREATE INDEX idx_invite_links_email ON invite_links(email);

-- 13. Page insights (metrics snapshots)
CREATE TABLE page_insights (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  page_id       UUID NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
  org_id        UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  period_start  DATE NOT NULL,
  period_end    DATE NOT NULL,
  views         BIGINT DEFAULT 0,
  viewers       BIGINT DEFAULT 0,
  follows       INTEGER DEFAULT 0,
  unfollows     INTEGER DEFAULT 0,
  visits        BIGINT DEFAULT 0,
  interactions  BIGINT DEFAULT 0,
  link_clicks   BIGINT DEFAULT 0,
  video_views   BIGINT DEFAULT 0,
  watch_time_seconds BIGINT DEFAULT 0,
  reactions     BIGINT DEFAULT 0,
  comments      BIGINT DEFAULT 0,
  shares        BIGINT DEFAULT 0,
  fetched_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(page_id, period_start, period_end)
);
CREATE INDEX idx_insights_page ON page_insights(page_id);
CREATE INDEX idx_insights_period ON page_insights(period_start, period_end);

-- 14. Revenue records (earnings data from Meta)
CREATE TABLE revenue_records (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  page_id       UUID NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
  org_id        UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  date          DATE NOT NULL,
  total_cents   BIGINT NOT NULL DEFAULT 0, -- store in cents to avoid float issues
  reels_cents   BIGINT NOT NULL DEFAULT 0,
  photos_cents  BIGINT NOT NULL DEFAULT 0,
  stories_cents BIGINT NOT NULL DEFAULT 0,
  text_cents    BIGINT NOT NULL DEFAULT 0,
  views         BIGINT NOT NULL DEFAULT 0,
  currency      TEXT NOT NULL DEFAULT 'USD',
  fetched_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(page_id, date)
);
CREATE INDEX idx_revenue_page ON revenue_records(page_id);
CREATE INDEX idx_revenue_date ON revenue_records(date);

-- 15. Post insights (per-post performance after publishing)
CREATE TABLE post_insights (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  post_id       UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
  views         BIGINT DEFAULT 0,
  reach         BIGINT DEFAULT 0,
  clicks        BIGINT DEFAULT 0,
  reactions     BIGINT DEFAULT 0,
  comments      INTEGER DEFAULT 0,
  shares        INTEGER DEFAULT 0,
  revenue_cents BIGINT DEFAULT 0,
  fetched_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(post_id)
);
CREATE INDEX idx_post_insights_post ON post_insights(post_id);

-- ============================================================
-- UPDATED_AT TRIGGER
-- ============================================================

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to all tables with updated_at
CREATE TRIGGER trg_organizations_updated BEFORE UPDATE ON organizations FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_users_updated BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_batches_updated BEFORE UPDATE ON batches FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_pages_updated BEFORE UPDATE ON pages FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_posting_ids_updated BEFORE UPDATE ON posting_ids FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_posts_updated BEFORE UPDATE ON posts FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_team_members_updated BEFORE UPDATE ON team_members FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================
-- HELPER FUNCTIONS
-- ============================================================

-- Check if batch deletion is allowed (no active pages or drafts)
CREATE OR REPLACE FUNCTION check_batch_deletable()
RETURNS TRIGGER AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM pages WHERE batch_id = OLD.id AND is_active = true) THEN
    RAISE EXCEPTION 'Cannot delete batch with active pages';
  END IF;
  IF EXISTS (
    SELECT 1 FROM posts p
    JOIN pages pg ON p.page_id = pg.id
    WHERE pg.batch_id = OLD.id AND p.status IN ('draft', 'pending_approval', 'queued', 'publishing')
  ) THEN
    RAISE EXCEPTION 'Cannot delete batch with active drafts or queued posts';
  END IF;
  RETURN OLD;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_batch_delete_check BEFORE DELETE ON batches FOR EACH ROW EXECUTE FUNCTION check_batch_deletable();

-- Prevent retired posting IDs from being un-retired
CREATE OR REPLACE FUNCTION prevent_unretire()
RETURNS TRIGGER AS $$
BEGIN
  IF OLD.status = 'retired' AND NEW.status != 'retired' THEN
    RAISE EXCEPTION 'Retired posting IDs cannot be reactivated';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_posting_id_no_unretire BEFORE UPDATE ON posting_ids FOR EACH ROW EXECUTE FUNCTION prevent_unretire();
