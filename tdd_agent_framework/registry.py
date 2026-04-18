from __future__ import annotations

from typing import Any

from .core import BaseAgent


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent[Any, Any]] = {}

    def register(self, agent: BaseAgent[Any, Any]) -> None:
        if agent.name in self._agents:
            raise ValueError(f"agent already registered: {agent.name}")
        self._agents[agent.name] = agent

    def get(self, agent_name: str) -> BaseAgent[Any, Any]:
        try:
            return self._agents[agent_name]
        except KeyError as exc:
            raise KeyError(f"unknown agent: {agent_name}") from exc

    def has(self, agent_name: str) -> bool:
        return agent_name in self._agents

    def list_names(self) -> list[str]:
        return sorted(self._agents.keys())
