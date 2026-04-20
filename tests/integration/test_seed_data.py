"""Integration test for the rich seed data generator.

Verifies that running `python -m scripts.generate_seed_data` produces:
  - 1 organization (matched by clerk_org_id)
  - 35+ pages
  - 120+ posts
  - 90 days of page_insights per page (35 * 90 = 3150 minimum)

Marked `integration` so it's skipped by unit test runs. Requires a real
Supabase/Postgres DATABASE_URL to be reachable.
"""
from __future__ import annotations

import os
import subprocess
import sys

import pytest


@pytest.mark.integration
def test_seed_generates_expected_counts(db_cursor):
    # Run the seed script as a module from the backend/ directory.
    backend_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..")
    )
    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "scripts.generate_seed_data",
            "--org-id",
            "org_seed_test",
            "--email",
            "seed@demo.local",
        ],
        cwd=backend_root,
    )

    db_cursor.execute(
        "SELECT id FROM organizations WHERE clerk_org_id = %s",
        ("org_seed_test",),
    )
    row = db_cursor.fetchone()
    assert row is not None, "organization was not created"
    org_uuid = row["id"]

    db_cursor.execute(
        "SELECT COUNT(*) AS n FROM pages WHERE org_id = %s", (org_uuid,)
    )
    assert db_cursor.fetchone()["n"] >= 35

    db_cursor.execute(
        "SELECT COUNT(*) AS n FROM posts WHERE org_id = %s", (org_uuid,)
    )
    assert db_cursor.fetchone()["n"] >= 120

    db_cursor.execute(
        """
        SELECT COUNT(*) AS n
        FROM page_insights pi
        JOIN pages p ON p.id = pi.page_id
        WHERE p.org_id = %s
        """,
        (org_uuid,),
    )
    assert db_cursor.fetchone()["n"] >= 35 * 90

    db_cursor.execute(
        """
        SELECT COUNT(*) AS n
        FROM revenue_records rr
        JOIN pages p ON p.id = rr.page_id
        WHERE p.org_id = %s
        """,
        (org_uuid,),
    )
    assert db_cursor.fetchone()["n"] >= 35 * 90

    db_cursor.execute(
        "SELECT COUNT(*) AS n FROM batches WHERE org_id = %s", (org_uuid,)
    )
    assert db_cursor.fetchone()["n"] >= 5

    db_cursor.execute(
        "SELECT COUNT(*) AS n FROM posting_ids WHERE org_id = %s", (org_uuid,)
    )
    assert db_cursor.fetchone()["n"] >= 8
