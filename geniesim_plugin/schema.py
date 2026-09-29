"""Canonical JSON types shared by GenieSim G2 planning methods.

Positions use metres in the scene world frame. Orientations use normalized
Hamilton quaternions in (x, y, z, w) order. These types describe proposals;
they do not command a robot.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
from typing import Any, Mapping

MAX_WAYPOINTS = 32
POSITION_LIMIT_M = 2.0
QUATERNION_TOLERANCE = 1e-3


def _finite_vector(value: Any, length: int, name: str) -> tuple[float, ...]:
    if not isinstance(value, (list, tuple)) or len(value) != length:
        raise ValueError(f"{name} must contain {length} numbers")
    result = tuple(float(item) for item in value)
    if not all(math.isfinite(item) for item in result):
        raise ValueError(f"{name} values must be finite")
    return result


@dataclass(frozen=True)
class Pose:
    position_m: tuple[float, float, float]
    orientation_xyzw: tuple[float, float, float, float]

    def __post_init__(self) -> None:
        position = _finite_vector(self.position_m, 3, "position_m")
        orientation = _finite_vector(self.orientation_xyzw, 4, "orientation_xyzw")
        if any(abs(v) > POSITION_LIMIT_M for v in position):
            raise ValueError(f"position_m components must be within ±{POSITION_LIMIT_M} m")
        norm = math.sqrt(sum(v * v for v in orientation))
        if abs(norm - 1.0) > QUATERNION_TOLERANCE:
            raise ValueError("orientation_xyzw must be a normalized quaternion")
        object.__setattr__(self, "position_m", position)
        object.__setattr__(self, "orientation_xyzw", tuple(v / norm for v in orientation))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Pose":
        return cls(tuple(data["position_m"]), tuple(data["orientation_xyzw"]))

    def to_dict(self) -> dict[str, list[float]]:
        return {"position_m": list(self.position_m), "orientation_xyzw": list(self.orientation_xyzw)}


@dataclass(frozen=True)
class Waypoint:
    pose: Pose
    gripper: str

    def __post_init__(self) -> None:
        if self.gripper not in {"open", "closed", "holding"}:
            raise ValueError("gripper must be open, closed, or holding")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Waypoint":
        return cls(Pose.from_dict(data["pose"]), data["gripper"])

    def to_dict(self) -> dict[str, Any]:
        return {"pose": self.pose.to_dict(), "gripper": self.gripper}


@dataclass(frozen=True)
class Plan:
    task: str
    arm: str
    frame: str
    position_unit: str
    quaternion_order: str
    waypoints: tuple[Waypoint, ...]
    source_method: str
    status: str = "proposed_unexecuted"

    def __post_init__(self) -> None:
        if self.task != "place_block_into_box":
            raise ValueError("unsupported task")
        if self.arm != "left":
            raise ValueError("this adapter supports the G2 left arm only")
        if (self.frame, self.position_unit, self.quaternion_order) != ("world", "m", "xyzw"):
            raise ValueError("plan must use world frame, metres, and xyzw quaternions")
        if not 1 <= len(self.waypoints) <= MAX_WAYPOINTS:
            raise ValueError(f"waypoints must contain 1 to {MAX_WAYPOINTS} entries")
        if not self.source_method:
            raise ValueError("source_method is required")
        if self.status != "proposed_unexecuted":
            raise ValueError("plans must remain marked proposed_unexecuted")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Plan":
        if data.get("schema_version") != "geniesim-g2-plan/1":
            raise ValueError("unsupported or missing schema_version")
        return cls(
            task=data["task"], arm=data["arm"], frame=data["frame"],
            position_unit=data["position_unit"], quaternion_order=data["quaternion_order"],
            waypoints=tuple(Waypoint.from_dict(item) for item in data["waypoints"]),
            source_method=data["source_method"], status=data.get("status", "proposed_unexecuted"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "geniesim-g2-plan/1", "task": self.task, "arm": self.arm,
            "frame": self.frame, "position_unit": self.position_unit,
            "quaternion_order": self.quaternion_order,
            "waypoints": [waypoint.to_dict() for waypoint in self.waypoints],
            "source_method": self.source_method, "status": self.status,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, allow_nan=False) + "\n"


@dataclass(frozen=True)
class Observation:
    task: str
    instruction: str
    arm: str
    objects: Mapping[str, Pose]
    image_paths: Mapping[str, str] = field(default_factory=dict)
    history: tuple[Mapping[str, Any], ...] = ()

    def __post_init__(self) -> None:
        if self.task != "place_block_into_box" or self.arm != "left":
            raise ValueError("observation must describe the supported left-arm placement task")
        required = {"benchmark_building_blocks_e4e8268e", "benchmark_building_blocks_0f256c95"}
        if not required.issubset(self.objects):
            raise ValueError("observation is missing target block or container")
        if not all(isinstance(name, str) and isinstance(path, str) for name, path in self.image_paths.items()):
            raise ValueError("image_paths must map camera names to paths")
        if len(self.history) > 64 or not all(isinstance(item, Mapping) for item in self.history):
            raise ValueError("history must contain at most 64 structured entries")

    def to_dict(self) -> dict[str, Any]:
        return {"task": self.task, "instruction": self.instruction, "arm": self.arm,
                "objects": {key: value.to_dict() for key, value in self.objects.items()},
                "image_paths": dict(self.image_paths), "history": list(self.history)}
