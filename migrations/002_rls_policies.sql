-- MetaReverse — Row Level Security Policies
-- The backend uses service_role key (bypasses RLS) for all writes.
-- RLS is a defense-in-depth layer: if anon key ever leaks, data is still scoped.
-- All policies scope by org_id extracted from JWT claims.

-- ============================================================
-- ENABLE RLS ON ALL TABLES
-- ============================================================

ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE batches ENABLE ROW LEVEL SECURITY;
ALTER TABLE pages ENABLE ROW LEVEL SECURITY;
ALTER TABLE posting_ids ENABLE ROW LEVEL SECURITY;
ALTER TABLE page_posting_id_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE posts ENABLE ROW LEVEL SECURITY;
ALTER TABLE post_media ENABLE ROW LEVEL SECURITY;
ALTER TABLE thread_comments ENABLE ROW LEVEL SECURITY;
ALTER TABLE approvals ENABLE ROW LEVEL SECURITY;
ALTER TABLE team_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE invite_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE page_insights ENABLE ROW LEVEL SECURITY;
ALTER TABLE revenue_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE post_insights ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- HELPER: Extract org_id from JWT
-- Clerk JWT has org_id in metadata. We store it as a claim.
-- The backend sets this via set_config before queries when using anon key.
-- ============================================================

CREATE OR REPLACE FUNCTION current_org_id() RETURNS UUID AS $$
BEGIN
  RETURN NULLIF(current_setting('app.current_org_id', true), '')::UUID;
END;
$$ LANGUAGE plpgsql STABLE;

CREATE OR REPLACE FUNCTION current_user_id() RETURNS UUID AS $$
BEGIN
  RETURN NULLIF(current_setting('app.current_user_id', true), '')::UUID;
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================
-- POLICIES: Organizations
-- ============================================================

CREATE POLICY org_select ON organizations
  FOR SELECT USING (id = current_org_id());

-- ============================================================
-- POLICIES: Users
-- ============================================================

CREATE POLICY users_select ON users
  FOR SELECT USING (org_id = current_org_id());

-- ============================================================
-- POLICIES: Batches
-- ============================================================

CREATE POLICY batches_select ON batches
  FOR SELECT USING (org_id = current_org_id());

CREATE POLICY batches_insert ON batches
  FOR INSERT WITH CHECK (org_id = current_org_id());

CREATE POLICY batches_update ON batches
  FOR UPDATE USING (org_id = current_org_id());

CREATE POLICY batches_delete ON batches
  FOR DELETE USING (org_id = current_org_id());

-- ============================================================
-- POLICIES: Pages
-- ============================================================

CREATE POLICY pages_select ON pages
  FOR SELECT USING (org_id = current_org_id());

CREATE POLICY pages_insert ON pages
  FOR INSERT WITH CHECK (org_id = current_org_id());

CREATE POLICY pages_update ON pages
  FOR UPDATE USING (org_id = current_org_id());

-- ============================================================
-- POLICIES: Posting IDs
-- ============================================================

CREATE POLICY posting_ids_select ON posting_ids
  FOR SELECT USING (org_id = current_org_id());

CREATE POLICY posting_ids_insert ON posting_ids
  FOR INSERT WITH CHECK (org_id = current_org_id());

CREATE POLICY posting_ids_update ON posting_ids
  FOR UPDATE USING (org_id = current_org_id());

-- ============================================================
-- POLICIES: Page-PostingID Assignments
-- ============================================================

CREATE POLICY ppia_select ON page_posting_id_assignments
  FOR SELECT USING (
    EXISTS (SELECT 1 FROM pages WHERE pages.id = page_id AND pages.org_id = current_org_id())
  );

-- ============================================================
-- POLICIES: Posts
-- ============================================================

CREATE POLICY posts_select ON posts
  FOR SELECT USING (org_id = current_org_id());

CREATE POLICY posts_insert ON posts
  FOR INSERT WITH CHECK (org_id = current_org_id());

CREATE POLICY posts_update ON posts
  FOR UPDATE USING (org_id = current_org_id());

CREATE POLICY posts_delete ON posts
  FOR DELETE USING (org_id = current_org_id());

-- ============================================================
-- POLICIES: Post Media
-- ============================================================

CREATE POLICY post_media_select ON post_media
  FOR SELECT USING (org_id = current_org_id());

CREATE POLICY post_media_insert ON post_media
  FOR INSERT WITH CHECK (org_id = current_org_id());

CREATE POLICY post_media_delete ON post_media
  FOR DELETE USING (org_id = current_org_id());

-- ============================================================
-- POLICIES: Thread Comments
-- ============================================================

CREATE POLICY thread_comments_select ON thread_comments
  FOR SELECT USING (
    EXISTS (SELECT 1 FROM posts WHERE posts.id = post_id AND posts.org_id = current_org_id())
  );

-- ============================================================
-- POLICIES: Approvals
-- ============================================================

CREATE POLICY approvals_select ON approvals
  FOR SELECT USING (
    EXISTS (SELECT 1 FROM posts WHERE posts.id = post_id AND posts.org_id = current_org_id())
  );

-- ============================================================
-- POLICIES: Team Members
-- ============================================================

CREATE POLICY team_members_select ON team_members
  FOR SELECT USING (org_id = current_org_id());

CREATE POLICY team_members_insert ON team_members
  FOR INSERT WITH CHECK (org_id = current_org_id());

CREATE POLICY team_members_update ON team_members
  FOR UPDATE USING (org_id = current_org_id());

-- ============================================================
-- POLICIES: Invite Links
-- ============================================================

CREATE POLICY invite_links_select ON invite_links
  FOR SELECT USING (org_id = current_org_id());

CREATE POLICY invite_links_insert ON invite_links
  FOR INSERT WITH CHECK (org_id = current_org_id());

CREATE POLICY invite_links_update ON invite_links
  FOR UPDATE USING (org_id = current_org_id());

-- ============================================================
-- POLICIES: Page Insights
-- ============================================================

CREATE POLICY page_insights_select ON page_insights
  FOR SELECT USING (org_id = current_org_id());

-- ============================================================
-- POLICIES: Revenue Records
-- ============================================================

CREATE POLICY revenue_records_select ON revenue_records
  FOR SELECT USING (org_id = current_org_id());

-- ============================================================
-- POLICIES: Post Insights
-- ============================================================

CREATE POLICY post_insights_select ON post_insights
  FOR SELECT USING (
    EXISTS (SELECT 1 FROM posts WHERE posts.id = post_id AND posts.org_id = current_org_id())
  );
