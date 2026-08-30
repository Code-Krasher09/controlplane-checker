"""Redis foundation and runtime state store tests."""

import pytest
from app.persistence.redis import RuntimeStateStore


@pytest.mark.asyncio
async def test_redis_state_store_retry_counters():
    """Test retry count incrementing, retrieval, and reset."""
    store = RuntimeStateStore()
    request_id = "test-req-123"

    # Initial count
    count = await store.get_retry_count(request_id)
    assert count == 0

    # Increment
    new_count = await store.increment_retry_count(request_id)
    assert new_count == 1
    new_count_2 = await store.increment_retry_count(request_id)
    assert new_count_2 == 2

    # Reset
    await store.reset_retry_count(request_id)
    assert await store.get_retry_count(request_id) == 0


@pytest.mark.asyncio
async def test_redis_state_store_budgets():
    """Test request, session, and adjudication budget tracking."""
    store = RuntimeStateStore()
    req_id = "req-456"
    sess_id = "sess-789"

    # Request budget
    assert await store.get_request_budget(req_id) == 0.0
    await store.consume_request_budget(req_id, 0.0015)
    await store.consume_request_budget(req_id, 0.0020)
    assert round(await store.get_request_budget(req_id), 4) == 0.0035

    # Session budget
    assert await store.get_session_budget(sess_id) == 0.0
    await store.consume_session_budget(sess_id, 0.012)
    assert round(await store.get_session_budget(sess_id), 3) == 0.012

    # Adjudication budget
    assert await store.get_adjudication_budget(sess_id) == 0.0
    await store.consume_adjudication_budget(sess_id, 0.008)
    assert round(await store.get_adjudication_budget(sess_id), 3) == 0.008


@pytest.mark.asyncio
async def test_redis_ping_health():
    """Test ping returns True (whether connected to live Redis or in-memory fallback)."""
    store = RuntimeStateStore()
    is_healthy = await store.ping()
    assert is_healthy is True
