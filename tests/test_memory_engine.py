"""
tests/test_memory_engine.py
Tests for the Personal AI Memory Engine.
"""

import pytest
from services.memory_engine import (
    set_memory, get_memory, search_memories, delete_memory,
    list_memories, clear_user_memories, MEMORY_TYPES, Memory,
)


def test_set_and_get_memory():
    """Set a memory and retrieve it."""
    mem = set_memory(1, "preference", "theme", "dark mode")
    assert mem.user_id == 1
    assert mem.memory_type == "preference"
    assert mem.key == "theme"
    assert mem.value == "dark mode"

    retrieved = get_memory(1, "preference", "theme")
    assert retrieved is not None
    assert retrieved.value == "dark mode"


def test_get_nonexistent_memory():
    """Getting a memory that doesn't exist returns None."""
    result = get_memory(999, "preference", "nonexistent")
    assert result is None


def test_set_memory_invalid_type():
    """Invalid memory type should raise ValueError."""
    with pytest.raises(ValueError):
        set_memory(1, "invalid_type", "key", "value")


def test_set_memory_empty_key():
    """Empty key should raise ValueError."""
    with pytest.raises(ValueError):
        set_memory(1, "preference", "", "value")


def test_set_memory_empty_value():
    """Empty value should raise ValueError."""
    with pytest.raises(ValueError):
        set_memory(1, "preference", "key", "")


def test_set_memory_too_long():
    """Value over 10000 chars should raise ValueError."""
    with pytest.raises(ValueError):
        set_memory(1, "preference", "key", "x" * 10001)


def test_delete_memory():
    """Delete should remove the memory and return True."""
    set_memory(1, "preference", "to_delete", "value")
    assert delete_memory(1, "preference", "to_delete") is True
    assert get_memory(1, "preference", "to_delete") is None


def test_delete_nonexistent_memory():
    """Deleting a non-existent memory returns False."""
    assert delete_memory(999, "preference", "nonexistent") is False


def test_search_memories():
    """Search should find memories by keyword."""
    set_memory(1, "preference", "language", "Python is great")
    set_memory(1, "preference", "editor", "VS Code is nice")
    results = search_memories(1, "Python")
    assert len(results) >= 1
    assert any("Python" in m.value for m in results)


def test_search_memories_by_type():
    """Search can filter by memory type."""
    set_memory(1, "preference", "test_pref", "test value")
    set_memory(1, "task", "test_task", "test task value")
    results = search_memories(1, "test", memory_type="preference")
    assert all(m.memory_type == "preference" for m in results)


def test_search_empty_query():
    """Empty query returns empty list."""
    set_memory(1, "preference", "test", "value")
    assert search_memories(1, "") == []


def test_list_memories():
    """List should return all memories for a user."""
    clear_user_memories(1)
    set_memory(1, "preference", "key1", "value1")
    set_memory(1, "preference", "key2", "value2")
    results = list_memories(1)
    assert len(results) == 2


def test_list_memories_by_type():
    """List filtered by type returns only that type."""
    clear_user_memories(1)
    set_memory(1, "preference", "key1", "value1")
    set_memory(1, "task", "key2", "value2")
    results = list_memories(1, memory_type="preference")
    assert all(m.memory_type == "preference" for m in results)


def test_clear_user_memories():
    """Clear should remove all memories for a user."""
    set_memory(1, "preference", "key1", "value1")
    set_memory(1, "task", "key2", "value2")
    count = clear_user_memories(1)
    assert count >= 2
    assert list_memories(1) == []


def test_user_isolation():
    """Memories from one user should not be visible to another."""
    set_memory(1, "preference", "user1_key", "user1 value")
    set_memory(2, "preference", "user2_key", "user2 value")
    assert get_memory(1, "preference", "user2_key") is None
    assert get_memory(2, "preference", "user1_key") is None


def test_update_existing_memory():
    """Setting a memory with same type+key should update, not duplicate."""
    set_memory(1, "preference", "theme", "dark")
    set_memory(1, "preference", "theme", "light")
    mem = get_memory(1, "preference", "theme")
    assert mem.value == "light"
    results = list_memories(1, memory_type="preference")
    theme_count = sum(1 for m in results if m.key == "theme")
    assert theme_count == 1


def test_all_memory_types_valid():
    """All memory types should be in the valid set."""
    assert "short_term" in MEMORY_TYPES
    assert "task" in MEMORY_TYPES
    assert "preference" in MEMORY_TYPES
    assert "project" in MEMORY_TYPES


def test_short_term_memory():
    """Short-term memories should be stored and retrievable."""
    set_memory(1, "short_term", "ctx_1", "User asked about tasks")
    mem = get_memory(1, "short_term", "ctx_1")
    assert mem is not None
    assert mem.value == "User asked about tasks"


def test_memory_types_isolated():
    """Same key with different types should be separate memories."""
    set_memory(1, "preference", "test", "pref value")
    set_memory(1, "task", "test", "task value")
    assert get_memory(1, "preference", "test").value == "pref value"
    assert get_memory(1, "task", "test").value == "task value"
