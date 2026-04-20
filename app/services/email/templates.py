from string import Template

_BASE = """
<!doctype html>
<html><body style="font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:#F5F5F7;padding:24px;">
<div style="max-width:560px;margin:0 auto;background:#fff;border-radius:12px;padding:32px;border:1px solid #E4E4E7;">
  <div style="font-size:14px;font-weight:600;color:#18181B;margin-bottom:16px;">MetaReverse</div>
  $body
  <div style="margin-top:32px;padding-top:16px;border-top:1px solid #E4E4E7;color:#71717A;font-size:12px;">
    You received this because you are a member of a MetaReverse organization.
  </div>
</div></body></html>
"""

_TEMPLATES = {
    "invite": ("You're invited to $org_name on MetaReverse", """
<p style="font-size:15px;color:#27272A;">$inviter invited you to <b>$org_name</b> on MetaReverse.</p>
<p style="font-size:14px;color:#52525B;">Accept by <b>$expires_at</b>. After that, your invite expires.</p>
<p><a href="$invite_url" style="display:inline-block;padding:10px 16px;background:#18181B;color:#fff;border-radius:8px;text-decoration:none;font-size:14px;">Accept invite</a></p>
"""),
    "token_expired": ("Action needed: Facebook token $severity for $page_name", """
<p style="font-size:15px;color:#27272A;">The Facebook token for <b>$page_name</b> is <b>$severity</b>.</p>
<p style="font-size:14px;color:#52525B;">Until the token is refreshed, scheduled posts on this page will not publish.</p>
<p><a href="https://dashboard-six-swart-26.vercel.app/settings/connections" style="display:inline-block;padding:10px 16px;background:#DC2626;color:#fff;border-radius:8px;text-decoration:none;font-size:14px;">Reconnect now</a></p>
"""),
    "post_failed": ("Publishing failed: $post_title", """
<p style="font-size:15px;color:#27272A;">A post failed to publish: <b>$post_title</b></p>
<p style="font-size:14px;color:#52525B;">Reason: $error_message</p>
<p><a href="https://dashboard-six-swart-26.vercel.app/failed-posts" style="display:inline-block;padding:10px 16px;background:#18181B;color:#fff;border-radius:8px;text-decoration:none;font-size:14px;">Review failed posts</a></p>
"""),
    "digest_daily": ("MetaReverse daily digest", """
<p style="font-size:15px;color:#27272A;">Here's what happened yesterday.</p>
<ul style="font-size:14px;color:#52525B;">
  <li>Published: <b>$stats_published</b></li>
  <li>Failed: <b>$stats_failed</b></li>
  <li>Pending approval: <b>$stats_pending</b></li>
</ul>
"""),
    "approval_requested": ("Approval requested: $post_title", """
<p style="font-size:15px;color:#27272A;">A new post needs your review: <b>$post_title</b></p>
<p><a href="https://dashboard-six-swart-26.vercel.app/approvals" style="display:inline-block;padding:10px 16px;background:#18181B;color:#fff;border-radius:8px;text-decoration:none;font-size:14px;">Review</a></p>
"""),
    "approval_action_taken": ("Your post was $action", """
<p style="font-size:15px;color:#27272A;"><b>$reviewer</b> $action your post: <b>$post_title</b></p>
<p><a href="https://dashboard-six-swart-26.vercel.app/drafts" style="display:inline-block;padding:10px 16px;background:#18181B;color:#fff;border-radius:8px;text-decoration:none;font-size:14px;">Open drafts</a></p>
"""),
}


def render_email(kind: str, data: dict) -> tuple[str, str]:
    if kind not in _TEMPLATES:
        raise ValueError(f"Unknown template: {kind}")
    subject_tpl, body_tpl = _TEMPLATES[kind]
    flat = dict(data)
    for key, val in list(data.items()):
        if isinstance(val, dict):
            for k, v in val.items():
                flat[f"{key}_{k}"] = v
    body = Template(body_tpl).safe_substitute(flat)
    html = Template(_BASE).safe_substitute(body=body)
    subject = Template(subject_tpl).safe_substitute(flat)
    return html, subject
