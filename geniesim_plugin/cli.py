"""Offline CLI that writes a proposed plan JSON without robot connections."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .schema import Plan, Pose, Waypoint
from .task import CONTAINER_ID, TARGET_ID, load_observation


def offline_proposal(observation) -> Plan:
    """Create a conservative geometric draft from pinned object centers."""
    block = observation.objects[TARGET_ID].position_m
    box = observation.objects[CONTAINER_ID].position_m
    identity = (0.0, 0.0, 0.0, 1.0)
    # Heights are draft offsets from object centers, not calibrated contact poses.
    points = [
        (block[0], block[1], block[2] + 0.12, "open"),
        (block[0], block[1], block[2] + 0.035, "open"),
        (block[0], block[1], block[2] + 0.035, "closed"),
        (block[0], block[1], block[2] + 0.15, "holding"),
        (box[0], box[1], box[2] + 0.16, "holding"),
        (box[0], box[1], box[2] + 0.07, "holding"),
        (box[0], box[1], box[2] + 0.07, "open"),
        (box[0], box[1], box[2] + 0.18, "open"),
    ]
    return Plan("place_block_into_box", "left", "world", "m", "xyzw",
                tuple(Waypoint(Pose((x, y, z), identity), grip) for x, y, z, grip in points),
                "offline_geometry_draft")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--head-image", type=Path, help="optional head RGB reference for future VLM methods")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true", help="required; writes proposal JSON only")
    args = parser.parse_args(argv)
    if not args.dry_run:
        parser.error("--dry-run is required; this plugin has no actuation path")
    observation = load_observation(args.manifest, args.selection, args.head_image)
    plan = offline_proposal(observation)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(plan.to_json(), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "status": plan.status,
                      "waypoint_count": len(plan.waypoints), "robot_moved": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
