"""Redis client abstraction and runtime budget/counter interface."""

import json
from typing import Any, Dict, Optional
import redis.asyncio as aioredis
from app.core.config import Settings, get_settings


class RuntimeStateStore:
    """Typed runtime interface for hot ephemeral state (retries, token/cost budgets, session risk).

    Uses an active Redis connection when reachable, with an in-memory fallback
    for isolated unit tests and local prototype execution.
    """

    _GLOBAL_USE_IN_MEMORY: bool = False
    _GLOBAL_REDIS: Optional[aioredis.Redis] = None

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self._redis: Optional[aioredis.Redis] = None
        self._in_memory: Dict[str, str] = {}
        self._use_in_memory: bool = RuntimeStateStore._GLOBAL_USE_IN_MEMORY

    async def get_client(self) -> Optional[aioredis.Redis]:
        """Return connected Redis client or initialize connection."""
        if self._use_in_memory or RuntimeStateStore._GLOBAL_USE_IN_MEMORY:
            return None

        if self._redis is None:
            if RuntimeStateStore._GLOBAL_REDIS is not None:
                self._redis = RuntimeStateStore._GLOBAL_REDIS
                return self._redis

            try:
                url = self.settings.redis_url or f"redis://{self.settings.redis_host}:{self.settings.redis_port}/{self.settings.redis_db}"
                client = aioredis.from_url(
                    url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=0.05,
                )
                await client.ping()
                self._redis = client
                RuntimeStateStore._GLOBAL_REDIS = client
            except Exception:
                # Fallback gracefully to in-memory mode for offline execution
                self._use_in_memory = True
                RuntimeStateStore._GLOBAL_USE_IN_MEMORY = True
                self._redis = None
        return self._redis

    async def ping(self) -> bool:
        """Check Redis connectivity."""
        try:
            client = await self.get_client()
            if client is not None:
                return bool(await client.ping())
            return True  # in-memory mock is healthy
        except Exception:
            return False

    # --- Retry Counters ---

    async def get_retry_count(self, request_id: str) -> int:
        """Get current repair retry count for request."""
        key = f"retry_count:{request_id}"
        client = await self.get_client()
        if client:
            val = await client.get(key)
            return int(val) if val is not None else 0
        return int(self._in_memory.get(key, "0"))

    async def increment_retry_count(self, request_id: str) -> int:
        """Increment and return repair retry count for request."""
        key = f"retry_count:{request_id}"
        client = await self.get_client()
        if client:
            return int(await client.incr(key))
        current = int(self._in_memory.get(key, "0")) + 1
        self._in_memory[key] = str(current)
        return current

    async def reset_retry_count(self, request_id: str) -> None:
        """Reset repair retry count for request."""
        key = f"retry_count:{request_id}"
        client = await self.get_client()
        if client:
            await client.delete(key)
        else:
            self._in_memory.pop(key, None)

    # --- Request Cost Budget ---

    async def get_request_budget(self, request_id: str) -> float:
        """Get consumed request cost in USD."""
        key = f"budget:request:{request_id}"
        client = await self.get_client()
        if client:
            val = await client.get(key)
            return float(val) if val is not None else 0.0
        return float(self._in_memory.get(key, "0.0"))

    async def consume_request_budget(self, request_id: str, cost: float) -> float:
        """Add cost to consumed request budget in USD."""
        key = f"budget:request:{request_id}"
        client = await self.get_client()
        if client:
            new_val = await client.incrbyfloat(key, cost)
            return float(new_val)
        current = float(self._in_memory.get(key, "0.0")) + cost
        self._in_memory[key] = str(current)
        return current

    # --- Session Cost Budget ---

    async def get_session_budget(self, session_id: str) -> float:
        """Get consumed session cost in USD."""
        key = f"budget:session:{session_id}"
        client = await self.get_client()
        if client:
            val = await client.get(key)
            return float(val) if val is not None else 0.0
        return float(self._in_memory.get(key, "0.0"))

    async def consume_session_budget(self, session_id: str, cost: float) -> float:
        """Add cost to consumed session budget in USD."""
        key = f"budget:session:{session_id}"
        client = await self.get_client()
        if client:
            new_val = await client.incrbyfloat(key, cost)
            return float(new_val)
        current = float(self._in_memory.get(key, "0.0")) + cost
        self._in_memory[key] = str(current)
        return current

    # --- Adjudication Cost Budget ---

    async def get_adjudication_budget(self, session_id: str) -> float:
        """Get consumed secondary adjudication cost in USD."""
        key = f"budget:adjudication:{session_id}"
        client = await self.get_client()
        if client:
            val = await client.get(key)
            return float(val) if val is not None else 0.0
        return float(self._in_memory.get(key, "0.0"))

    async def consume_adjudication_budget(self, session_id: str, cost: float) -> float:
        """Add cost to consumed adjudication budget in USD."""
        key = f"budget:adjudication:{session_id}"
        client = await self.get_client()
        if client:
            new_val = await client.incrbyfloat(key, cost)
            return float(new_val)
        current = float(self._in_memory.get(key, "0.0")) + cost
        self._in_memory[key] = str(current)
        return current

    # --- Session Risk State Accumulator ---

    async def get_session_risk_state(self, session_id: str) -> Dict[str, Any]:
        """Fetch accumulated session risk metrics."""
        key = f"session_risk:{session_id}"
        default_state: Dict[str, Any] = {
            "session_id": session_id,
            "score": 0.0,
            "turn_count": 0,
            "violations_count": 0,
            "contradictions_count": 0,
            "repairs_count": 0,
            "uncertainties_count": 0,
            "warnings_count": 0,
        }

        client = await self.get_client()
        if client:
            raw = await client.get(key)
            if raw:
                try:
                    return json.loads(raw)
                except Exception:
                    pass
            return default_state

        raw_in_mem = self._in_memory.get(key)
        if raw_in_mem:
            try:
                return json.loads(raw_in_mem)
            except Exception:
                pass
        return default_state

    async def update_session_risk_state(
        self,
        session_id: str,
        delta_score: float,
        event_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Atomically update session risk score and counters."""
        state = await self.get_session_risk_state(session_id)
        state["turn_count"] = int(state.get("turn_count", 0)) + 1
        state["score"] = round(max(0.0, float(state.get("score", 0.0)) + delta_score), 2)

        if event_type == "VIOLATION":
            state["violations_count"] = int(state.get("violations_count", 0)) + 1
        elif event_type == "CONTRADICTION":
            state["contradictions_count"] = int(state.get("contradictions_count", 0)) + 1
        elif event_type == "REPAIR":
            state["repairs_count"] = int(state.get("repairs_count", 0)) + 1
        elif event_type == "UNCERTAINTY":
            state["uncertainties_count"] = int(state.get("uncertainties_count", 0)) + 1
        elif event_type == "WARNING":
            state["warnings_count"] = int(state.get("warnings_count", 0)) + 1

        payload = json.dumps(state)
        key = f"session_risk:{session_id}"

        client = await self.get_client()
        if client:
            await client.set(key, payload, ex=86400)  # 24h TTL
        else:
            self._in_memory[key] = payload

        return state

    async def reset_session_risk_state(self, session_id: str) -> None:
        """Reset session risk accumulator."""
        key = f"session_risk:{session_id}"
        client = await self.get_client()
        if client:
            await client.delete(key)
        else:
            self._in_memory.pop(key, None)


_runtime_state_store: Optional[RuntimeStateStore] = None


def get_state_store() -> RuntimeStateStore:
    """Return singleton instance of RuntimeStateStore."""
    global _runtime_state_store
    if _runtime_state_store is None:
        _runtime_state_store = RuntimeStateStore()
    return _runtime_state_store

