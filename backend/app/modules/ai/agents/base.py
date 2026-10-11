"""
AegisAI AI Agents Module — Base Agent Architecture.

Provides:
- Agent base class with prompt orchestration
- Tool invocation hooks
- Dual-mode execution: Fast deterministic algorithmic core + Ollama LLM enhancement
- Structured reasoning steps tracking
"""

import json
import time
from typing import Any, cast
import httpx
import structlog

from app.core.config.settings import settings

logger = structlog.get_logger("aegis_ai.agents.base")


class BaseAgent:
    """
    Abstract Base Class for AegisAI Specialized Autonomous Domain Agents.
    """

    def __init__(self, agent_name: str, domain_role: str) -> None:
        self.agent_name = agent_name
        self.domain_role = domain_role
        self.base_url = settings.OLLAMA_BASE_URL
        self.model_name = settings.OLLAMA_MODEL
        self.timeout = min(12.0, float(settings.OLLAMA_TIMEOUT_SECONDS))

    async def call_llm(self, system_prompt: str, user_prompt: str) -> dict[str, Any] | None:
        """
        Attempts to call the local Ollama LLM provider for structured synthesis.
        Returns parsed JSON or None if Ollama is unreachable/fails.
        """
        full_prompt = (
            f"SYSTEM ROLE:\n{system_prompt}\n\n"
            f"USER QUERY & CONTEXT:\n{user_prompt}\n\n"
            "IMPORTANT: Respond ONLY with strict valid JSON. Do not include markdown code block ticks (no ```json). "
            "Never invent false IDs or unverified factual data."
        )

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model_name,
                        "prompt": full_prompt,
                        "stream": False,
                        "format": "json",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                raw = data.get("response", "{}").strip()
                if raw.startswith("```json"):
                    raw = raw[7:]
                if raw.startswith("```"):
                    raw = raw[3:]
                parsed = json.loads(raw.strip())
                if isinstance(parsed, dict):
                    return cast(dict[str, Any], parsed)
                return None
        except Exception as err:
            logger.debug(
                "agent_llm_call_fallback",
                agent=self.agent_name,
                error=str(err),
            )
            return None
