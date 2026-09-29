"""Verify the pinned G2 IK/FK and scene frame boundary without moving a robot.

Run through the isolated GenieSim/Isaac environment on the server. This probe
does not connect a trajectory executor or evaluate task success.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import runpy
import sys
import traceback


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--gpu", type=int, default=4)
    args = parser.parse_args()
    root = args.server_root.resolve()
    if not root.is_relative_to(Path("/home/data_ssd1/pyj").resolve()):
        parser.error("server root must stay under /home/data_ssd1/pyj")
    if not args.output.resolve().is_relative_to(root):
        parser.error("output must stay under the server root")

    # SimulationApp initializes the USD Python modules supplied by Isaac Sim.
    from isaacsim import SimulationApp

    app = SimulationApp({"headless": True, "active_gpu": args.gpu,
                         "physics_gpu": args.gpu, "multi_gpu": False,
                         "renderer": "RayTracedLighting"})
    try:
        import numpy as np
        from pxr import Gf, Usd, UsdGeom

        upstream = root / "upstream"
        sys.path.insert(0, str(upstream / "source/geniesim/utils"))
        from ikfk_utils import IKFKSolver

        initial = runpy.run_path(str(upstream / "source/geniesim/benchmark/config/robot_init_states.py"))["G2_DEFAULT_STATES"]
        arm = initial["init_arm"]
        solver = IKFKSolver(arm, initial["head_state"], initial["body_state"], robot_cfg="G2_omnipicker")
        print("PROBE_STAGE solver_ready", flush=True)
        start = solver.compute_eef(arm)
        print("PROBE_STAGE fk_ready", flush=True)
        left_target = np.asarray(start["left"], dtype=float).copy()
        left_target[0] += 0.05
        # The bundled solver has a 5 ms limit per call. A single call can stop
        # far from target; repeat the solve and check FK rather than accepting it.
        solver.left_solver.update_target_quat(
            left_target[:3], np.asarray(start["left"][4:] + start["left"][3:4]))
        position_error = float("inf")
        iterations_used = 0
        for iterations_used in range(1, 201):
            left_joints = solver.left_solver.solve()
            reached = solver.compute_eef(list(left_joints) + list(arm[7:]))["left"]
            position_error = float(np.linalg.norm(np.asarray(reached[:3]) - left_target[:3]))
            if position_error <= 0.005:
                break
        print("PROBE_STAGE ik_ready", iterations_used, position_error, flush=True)
        if position_error > 0.005:
            raise RuntimeError(f"left-arm IK/FK error {position_error:.6f} m exceeds 5 mm")

        scene = root / "outputs/g2_place_block_layout0/constructed_scene.usda"
        stage = Usd.Stage.Open(str(scene))
        print("PROBE_STAGE stage_open", flush=True)
        arm_base = stage.GetPrimAtPath("/genie/arm_base_link")
        if not arm_base.IsValid():
            raise RuntimeError("G2 arm_base_link missing from constructed USD")
        matrix = UsdGeom.Xformable(arm_base).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        world_start = matrix.Transform(Gf.Vec3d(*start["left"][:3]))
        roundtrip = matrix.GetInverse().Transform(world_start)
        frame_error = float(np.linalg.norm(np.asarray(roundtrip) - np.asarray(start["left"][:3])))
        if frame_error > 1e-6:
            raise RuntimeError(f"world/arm-base frame roundtrip error {frame_error:.9f} m")

        result = {
            "status": "ik_fk_and_frame_probe_passed_no_actuation",
            "source": "official GenieSim v3.0.3 G2 IK-SDK wheel and fixed scene USD",
            "gpu": args.gpu,
            "arm": "left",
            "arm_base_world_position_m": list(matrix.ExtractTranslation()),
            "initial_left_eef_arm_base_m": start["left"][:3],
            "initial_left_eef_world_m": list(world_start),
            "local_probe_offset_m": [0.05, 0, 0],
            "ik_fk_position_error_m": position_error,
            "ik_solve_calls": iterations_used,
            "frame_roundtrip_error_m": frame_error,
            "robot_moved": False,
            "policy_executed": False,
            "task_success": None,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print("GENIESIM_G2_IK_PROBE_OK", json.dumps(result), flush=True)
        return 0
    except BaseException:
        traceback.print_exc()
        raise
    finally:
        app.close()


if __name__ == "__main__":
    raise SystemExit(main())
