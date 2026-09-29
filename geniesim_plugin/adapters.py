"""Common planning boundary for LLM and externally supplied plans."""

from __future__ import annotations

from typing import Any, Mapping, Protocol

from .planner import ModelClient, plan_with_model
from .schema import Observation, Plan


class PlanningMethod(Protocol):
    def propose(self, observation: Observation) -> Plan: ...


class LMTGStructuredMethod:
    def __init__(self, client: ModelClient | Any):
        self.client = client

    def propose(self, observation: Observation) -> Plan:
        return plan_with_model(observation, self.client)


class ExistingWorkflowMethod:
    """Adapt a plan created by an existing workflow into the canonical schema."""

    def __init__(self, plan_data: Mapping[str, Any]):
        self.plan_data = plan_data

    def propose(self, observation: Observation) -> Plan:
        del observation  # validation of observed task objects is performed at the boundary
        data = dict(self.plan_data)
        data.setdefault("source_method", "existing_workflow")
        return Plan.from_dict(data)


def propose(method: PlanningMethod, observation: Observation) -> Plan:
    result = method.propose(observation)
    if not isinstance(result, Plan):
        raise TypeError("planning methods must return a validated Plan")
    return result
