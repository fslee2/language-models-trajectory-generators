"""Generate a G2 plan locally from privileged Genie Sim debug state.

This is an oracle-assisted integration test, not a vision-only policy result.
The DeepSeek key remains on the workstation; only validated plan JSON may be
copied to the server. No generated Python is evaluated.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import urllib.error
import urllib.request

from .adapters import LMTGStructuredMethod, propose
from .schema import Observation, Pose
from .task import CONTAINER_ID, TARGET_ID


class DeepSeekDebugClient:
    def __init__(self, key_file: Path, debug_context: dict):
        self.key_file = key_file
        self.debug_context = debug_context
        self.response_info = None

    def complete(self, prompt: str) -> str:
        key = self.key_file.read_text(encoding="utf-8-sig").strip()
        if not key or "\n" in key or "\r" in key:
            raise ValueError("API key file must contain one nonempty key")
        request_body = {
            "model": "deepseek-flash",
            "reasoning_effort": "low",
            "max_tokens": 8000,
            "response_format": {"type": "json_object"},
            "stream": False,
            "messages": [{"role": "system", "content": prompt + "\n\n"
                         "PRIVILEGED SIMULATOR DEBUG GEOMETRY (not camera perception):\n"
                         + json.dumps(self.debug_context, allow_nan=False) + "\n"
                         "Waypoints control the IK end-effector reference, not the gripper center. "
                         "Use the measured gripper-center minus end-effector offset to convert desired "
                         "gripper positions into end-effector positions. Preserve the supplied current "
                         "end-effector quaternion. Include the current pose first, approach from above, "
                         "then grasp, lift, move to the container, release, and retreat. "
                         "The box AABB is not a measured hole pose; do not invent a precise hole location. "
                         "Return valid JSON only."}],
        }
        request = urllib.request.Request(
            "https://api.deepseek.com/chat/completions",
            data=json.dumps(request_body).encode("utf-8"),
            headers={"Authorization": "Bearer " + key,
                     "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"DeepSeek API returned HTTP {exc.code}") from None
        choice = payload["choices"][0]
        self.response_info = {
            "requested_model": request_body["model"],
            "returned_model": payload.get("model"),
            "finish_reason": choice.get("finish_reason"),
            "usage": payload.get("usage"),
            "raw_content": choice["message"].get("content"),
            "privileged_debug_input": True,
            "camera_pixels_sent": False,
        }
        if self.response_info["finish_reason"] != "stop":
            raise ValueError("model response did not finish normally")
        return self.response_info["raw_content"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--privileged-state", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--approach-plan", type=Path, required=True)
    parser.add_argument("--key-file", type=Path,
                        default=Path("D:/Simpler/deepseek_api_key.txt"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    state = json.loads(args.privileged_state.read_text(encoding="utf-8"))
    selection = json.loads(args.selection.read_text(encoding="utf-8"))
    approach = json.loads(args.approach_plan.read_text(encoding="utf-8"))
    if (state.get("task"), state.get("layout"), state.get("arm")) != (
            "place_block_into_box", 0, "left"):
        parser.error("privileged state is not the selected G2 task")
    if state.get("policy_input") is not False:
        parser.error("privileged state must be explicitly marked diagnostic-only")
    if state.get("left_gripper_joint_positions", [0])[0] < 0.7:
        parser.error("scene snapshot must use the official open-gripper state")
    objects = {}
    for object_id, label in ((TARGET_ID, "target"), (CONTAINER_ID, "container")):
        box = state[label]
        center = [(lo + hi) / 2 for lo, hi in zip(box["aabb_min_m"], box["aabb_max_m"])]
        objects[object_id] = Pose(tuple(center), tuple(selection["objects"][object_id]["xyzw"]))
    observation = Observation(task="place_block_into_box",
                              instruction=selection["instruction"], arm="left",
                              objects=objects)
    current_pose = approach["waypoints"][0]["pose"]
    eef = current_pose["position_m"]
    gripper = state["left_gripper_center"]["origin_world_m"]
    debug_context = {
        "target_aabb_min_m": state["target"]["aabb_min_m"],
        "target_aabb_max_m": state["target"]["aabb_max_m"],
        "container_aabb_min_m": state["container"]["aabb_min_m"],
        "container_aabb_max_m": state["container"]["aabb_max_m"],
        "current_eef_world_m": eef,
        "current_eef_quaternion_xyzw": current_pose["orientation_xyzw"],
        "current_gripper_center_world_m": gripper,
        "gripper_center_minus_eef_world_m": [g - e for g, e in zip(gripper, eef)],
        "safe_clearance_above_target_m": 0.12,
        "target_id": TARGET_ID,
        "container_id": CONTAINER_ID,
    }
    client = DeepSeekDebugClient(args.key_file, debug_context)
    try:
        plan = propose(LMTGStructuredMethod(client), observation)
    finally:
        if client.response_info is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.with_suffix(".response.json").write_text(
                json.dumps(client.response_info, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8")
    args.output.write_text(plan.to_json(), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "waypoints": len(plan.waypoints),
                      "status": plan.status, "source_method": plan.source_method,
                      "privileged_debug_input": True, "robot_moved": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
