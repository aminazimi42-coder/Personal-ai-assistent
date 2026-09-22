"""
tests/test_tenant_service.py
Tests for tenant_service: create, membership, access control, isolation.
Uses in-memory store (no DB needed).
"""

import pytest
from services import tenant_service
from services.tenant_service import _reset_mem_store


@pytest.fixture(autouse=True)
def _reset():
    _reset_mem_store()
    yield
    _reset_mem_store()


# ------------------------------------------------------------------ #
# Create tenant
# ------------------------------------------------------------------ #

def test_create_tenant():
    tenant = tenant_service.create_tenant("My Company", 1)
    assert tenant["name"] == "My Company"
    assert tenant["owner_user_id"] == 1
    assert tenant["slug"] == "my-company"
    assert tenant["id"] is not None


def test_create_tenant_empty_name():
    with pytest.raises(ValueError, match="name is required"):
        tenant_service.create_tenant("", 1)


def test_create_tenant_slugify():
    tenant = tenant_service.create_tenant("Acme Corp! Inc.", 1)
    assert tenant["slug"] == "acme-corp-inc"


def test_create_tenant_unique_slug():
    t1 = tenant_service.create_tenant("Acme", 1)
    t2 = tenant_service.create_tenant("Acme", 2)
    assert t1["slug"] == "acme"
    assert t2["slug"].startswith("acme")
    assert t2["slug"] != t1["slug"]


# ------------------------------------------------------------------ #
# Membership
# ------------------------------------------------------------------ #

def test_add_member():
    tenant = tenant_service.create_tenant("Corp", 1)
    m = tenant_service.add_member(tenant["id"], 2, "admin")
    assert m["tenant_id"] == tenant["id"]
    assert m["user_id"] == 2
    assert m["role"] == "admin"


def test_add_member_invalid_role():
    tenant = tenant_service.create_tenant("Corp", 1)
    with pytest.raises(ValueError, match="Invalid role"):
        tenant_service.add_member(tenant["id"], 2, "superadmin")


def test_add_member_upsert_existing():
    """Adding an existing member updates their role."""
    tenant = tenant_service.create_tenant("Corp", 1)
    m1 = tenant_service.add_member(tenant["id"], 2, "member")
    m2 = tenant_service.add_member(tenant["id"], 2, "admin")
    assert m2["role"] == "admin"
    members = tenant_service.list_members(tenant["id"], 1)
    assert len(members) == 2  # owner + user 2


# ------------------------------------------------------------------ #
# List members
# ------------------------------------------------------------------ #

def test_list_members():
    tenant = tenant_service.create_tenant("Corp", 1)
    tenant_service.add_member(tenant["id"], 2, "admin")
    tenant_service.add_member(tenant["id"], 3, "member")
    members = tenant_service.list_members(tenant["id"], 1)
    assert len(members) == 3  # owner + 2 added


def test_list_members_access_denied():
    """Non-member cannot list members."""
    tenant = tenant_service.create_tenant("Corp", 1)
    with pytest.raises(PermissionError):
        tenant_service.list_members(tenant["id"], 999)


# ------------------------------------------------------------------ #
# Access control
# ------------------------------------------------------------------ #

def test_check_tenant_access_owner():
    tenant = tenant_service.create_tenant("Corp", 1)
    assert tenant_service.check_tenant_access(tenant["id"], 1) is True


def test_check_tenant_access_member():
    tenant = tenant_service.create_tenant("Corp", 1)
    tenant_service.add_member(tenant["id"], 2, "member")
    assert tenant_service.check_tenant_access(tenant["id"], 2) is True


def test_check_tenant_access_non_member():
    tenant = tenant_service.create_tenant("Corp", 1)
    assert tenant_service.check_tenant_access(tenant["id"], 999) is False


def test_check_tenant_access_nonexistent_tenant():
    assert tenant_service.check_tenant_access(999, 1) is False


# ------------------------------------------------------------------ #
# Get user tenants
# ------------------------------------------------------------------ #

def test_get_user_tenants():
    t1 = tenant_service.create_tenant("T1", 1)
    t2 = tenant_service.create_tenant("T2", 1)
    tenant_service.add_member(t2["id"], 2, "admin")
    tenants_1 = tenant_service.get_user_tenants(1)
    assert len(tenants_1) == 2
    tenants_2 = tenant_service.get_user_tenants(2)
    assert len(tenants_2) == 1
    assert tenants_2[0]["name"] == "T2"


def test_get_user_tenants_empty():
    assert tenant_service.get_user_tenants(999) == []


# ------------------------------------------------------------------ #
# Isolation
# ------------------------------------------------------------------ #

def test_tenant_isolation():
    """User 2 cannot access user 1's tenant unless added as member."""
    tenant = tenant_service.create_tenant("User1 Corp", 1)
    assert tenant_service.check_tenant_access(tenant["id"], 2) is False
    tenant_service.add_member(tenant["id"], 2, "member")
    assert tenant_service.check_tenant_access(tenant["id"], 2) is True


def test_get_tenant():
    tenant = tenant_service.create_tenant("Corp", 1)
    fetched = tenant_service.get_tenant(tenant["id"])
    assert fetched is not None
    assert fetched["name"] == "Corp"


def test_get_tenant_not_found():
    assert tenant_service.get_tenant(999) is None
