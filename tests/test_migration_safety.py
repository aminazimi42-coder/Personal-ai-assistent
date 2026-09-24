"""
tests/test_migration_safety.py
Tests for migration safety: verify migration files parse, verify
the migration chain, and test that the upgrade path is safe for
existing data (user_id nullability, FK constraints, additive only).
"""

import ast
import os
import pytest


MIGRATIONS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "migrations", "versions"
)


def _load_migration_file(filename):
    """Load and parse a migration file."""
    path = os.path.join(MIGRATIONS_DIR, filename)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        content = f.read()
    return content


def test_migration_001_parses_as_valid_python():
    """001_initial_schema.py must parse as valid Python."""
    content = _load_migration_file("001_initial_schema.py")
    assert content is not None
    ast.parse(content)


def test_migration_002_parses_as_valid_python():
    """002_upgrade_existing_schema.py must parse as valid Python."""
    content = _load_migration_file("002_upgrade_existing_schema.py")
    assert content is not None
    ast.parse(content)


def test_migration_003_parses_as_valid_python():
    """003_add_ai_usage_events.py must parse as valid Python."""
    content = _load_migration_file("003_add_ai_usage_events.py")
    assert content is not None
    ast.parse(content)


def test_migration_chain_is_sequential():
    """Migrations must form a sequential chain: 001 → 002 → 003."""
    import importlib.util

    def load_module(name, filename):
        path = os.path.join(MIGRATIONS_DIR, filename)
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    m001 = load_module("m001", "001_initial_schema.py")
    m002 = load_module("m002", "002_upgrade_existing_schema.py")
    m003 = load_module("m003", "003_add_ai_usage_events.py")

    assert m001.revision == "001_initial_schema"
    assert m001.down_revision is None

    assert m002.revision == "002_upgrade_existing_schema"
    assert m002.down_revision == "001_initial_schema"

    assert m003.revision == "003_add_ai_usage_events"
    assert m003.down_revision == "002_upgrade_existing_schema"


def test_migration_001_user_id_not_null():
    """001 creates tasks.user_id as NOT NULL (fresh deployment)."""
    content = _load_migration_file("001_initial_schema.py")
    # The 001 migration creates user_id as nullable=False for new deployments
    assert 'sa.Column("user_id", sa.Integer(), nullable=False)' in content


def test_migration_002_user_id_additive():
    """002 adds user_id as nullable (additive, safe for existing rows)."""
    content = _load_migration_file("002_upgrade_existing_schema.py")
    # The 002 migration uses ADD COLUMN IF NOT EXISTS (additive)
    assert "ADD COLUMN IF NOT EXISTS user_id INTEGER" in content
    # It does NOT add NOT NULL constraint on user_id (safe for existing rows)
    assert "user_id INTEGER NOT NULL" not in content


def test_migration_002_fk_conditional():
    """002 adds FK only if it doesn't already exist (idempotent)."""
    content = _load_migration_file("002_upgrade_existing_schema.py")
    # Uses DO $$ BEGIN ... IF NOT EXISTS ... (conditional FK)
    assert "IF NOT EXISTS" in content
    assert "FOREIGN KEY" in content
    assert "DO $$" in content


def test_migration_002_upgrade_does_not_drop_tables():
    """002 upgrade must not drop any tables or columns (additive only)."""
    content = _load_migration_file("002_upgrade_existing_schema.py")
    # Only check the upgrade section
    upgrade_section = content.split("def downgrade")[0]
    assert "DROP TABLE" not in upgrade_section
    assert "DROP COLUMN" not in upgrade_section


def test_migration_003_additive_only():
    """003 must be purely additive (new table, no modifications to existing)."""
    content = _load_migration_file("003_add_ai_usage_events.py")
    # Must not alter existing tables
    assert "ALTER TABLE users" not in content
    assert "ALTER TABLE tasks" not in content
    assert "ALTER TABLE appointments" not in content
    assert "DROP TABLE" not in content.split("def downgrade")[0]  # upgrade section


def test_migration_003_has_proper_downgrade():
    """003 must have a proper downgrade (drop table + index)."""
    content = _load_migration_file("003_add_ai_usage_events.py")
    downgrade_section = content.split("def downgrade")[1]
    assert "drop_table" in downgrade_section or "DROP TABLE" in downgrade_section
    assert "drop_index" in downgrade_section or "DROP INDEX" in downgrade_section


def test_migration_001_has_downgrade():
    """001 must have a downgrade that drops all tables."""
    content = _load_migration_file("001_initial_schema.py")
    downgrade_section = content.split("def downgrade")[1]
    assert "drop_table" in downgrade_section


def test_all_migrations_have_upgrade_and_downgrade():
    """All migration files must have both upgrade() and downgrade() functions."""
    for filename in ["001_initial_schema.py", "002_upgrade_existing_schema.py",
                     "003_add_ai_usage_events.py"]:
        content = _load_migration_file(filename)
        assert content is not None
        assert "def upgrade()" in content
        assert "def downgrade()" in content


def test_migration_003_has_fk_to_users():
    """003 ai_usage_events must have FK to users.id with CASCADE."""
    content = _load_migration_file("003_add_ai_usage_events.py")
    assert "ForeignKeyConstraint" in content
    assert "users.id" in content
    assert "CASCADE" in content or "ondelete" in content.lower()


def test_migration_010_allows_pro_plus_plan():
    """010 must add 'pro_plus' to the subscriptions CHECK constraint.

    Root cause of /api/v1/account/quota 500 (H3): the subscriptions
    table had a CHECK constraint allowing only ('free', 'pro') but M1.1
    added a 'pro_plus' plan to the Plan model. When get_user_plan()
    resolved a pro_plus subscriber, PostgreSQL rejected the row and
    the exception bubbled up as a 500. This migration drops and recreates
    the constraint to include 'pro_plus'.
    """
    content = _load_migration_file("010_allow_pro_plus_plan.py")
    assert content is not None
    assert "pro_plus" in content
    assert "ck_subscriptions_plan" in content
    assert "DROP CONSTRAINT" in content
    assert "ADD CONSTRAINT" in content
    # The new constraint must include all three plans
    upgrade_section = content.split("def downgrade")[0]
    assert "'free'" in upgrade_section
    assert "'pro'" in upgrade_section
    assert "'pro_plus'" in upgrade_section
