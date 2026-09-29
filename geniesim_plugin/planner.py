"""Structured LMTG-inspired planner; model access is injected by the caller."""

from __future__ import annotations

import json
from typing import Any, Callable, Protocol

from .schema import Observation, Plan

SYSTEM_PROMPT = """You propose a staged end-effector pick-and-place trajectory inspired by the LMTG dense trajectory workflow. Return only one JSON object matching this schema: {\"schema_version\":\"geniesim-g2-plan/1\",\"task\":\"place_block_into_box\",\"arm\":\"left\",\"frame\":\"world\",\"position_unit\":\"m\",\"quaternion_order\":\"xyzw\",\"waypoints\":[{\"pose\":{\"position_m\":[x,y,z],\"orientation_xyzw\":[x,y,z,w]},\"gripper\":\"open|closed|holding\"}],\"source_method\":\"lmtg_structured\",\"status\":\"proposed_unexecuted\"}. Include at most 32 waypoints. Positions are world-frame metres; orientations are normalized Hamilton quaternions in xyzw order. The sequence should stage approach, grasp, lift, approach to the container, release, and retreat as appropriate. Use only supplied observation data. Image paths are file references, not visible pixel content in this text prompt. Do not emit code or claim execution/success."""


class ModelClient(Protocol):
    def complete(self, prompt: str) -> str | dict[str, Any]: ...


def build_prompt(observation: Observation) -> str:
    return SYSTEM_PROMPT + "\n\nOBSERVATION JSON:\n" + json.dumps(observation.to_dict(), allow_nan=False)


def plan_with_model(observation: Observation, client: ModelClient | Callable[[str], Any]) -> Plan:
    prompt = build_prompt(observation)
    raw = client.complete(prompt) if hasattr(client, "complete") else client(prompt)
    data = json.loads(raw) if isinstance(raw, str) else raw
    plan = Plan.from_dict(data)
    if plan.source_method != "lmtg_structured":
        raise ValueError("model plan source_method must be lmtg_structured")
    return plan
