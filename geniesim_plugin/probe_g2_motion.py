"""Move the pinned G2 left arm 5 cm in simulation and measure the result.

This is a bounded controller smoke test, not a pick/place policy or evaluation.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import runpy
import sys


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--server-root", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--gpu", type=int, default=4)
    a = p.parse_args()
    root = a.server_root.resolve()
    out = a.output_dir.resolve()
    if not root.is_relative_to(Path("/home/data_ssd1/pyj").resolve()) or not out.is_relative_to(root):
        p.error("all runtime paths must stay under /home/data_ssd1/pyj")
    out.mkdir(parents=True, exist_ok=True)

    from isaacsim import SimulationApp
    app = SimulationApp({"headless": True, "active_gpu": a.gpu, "physics_gpu": a.gpu,
                         "multi_gpu": False, "renderer": "RayTracedLighting",
                         "width": 640, "height": 400})
    try:
        import numpy as np
        from PIL import Image
        from scipy.spatial.transform import Rotation
        from pxr import Gf, Usd, UsdGeom
        from isaacsim.core.api import World
        from isaacsim.core.prims import SingleArticulation
        from isaacsim.core.utils.stage import add_reference_to_stage, get_current_stage
        from isaacsim.core.utils.types import ArticulationAction
        from isaacsim.sensors.camera import Camera
        from .schema import Plan, Pose, Waypoint

        repo = root / "upstream"
        assets = repo / "source/geniesim/assets"
        layout = repo / "source/geniesim/benchmark/config/llm_task/place_block_into_box/0"
        selection = json.loads((root / "configs/scene_selection.json").read_text())
        world = World(stage_units_in_meters=1, physics_dt=1 / 120, rendering_dt=1 / 30)
        add_reference_to_stage(str(assets / "background/room/room_1/background.usda"), "/World")
        add_reference_to_stage(str(layout / "scene.usda"), "/World")
        add_reference_to_stage(str(assets / "robot/G2_omnipicker/robot_fix.usda"), "/genie")
        robot = world.scene.add(SingleArticulation(
            prim_path="/genie", name="G2_omnipicker",
            position=np.asarray(selection["robot_position"], dtype=float),
            orientation=np.asarray(selection["robot_quaternion_wxyz"], dtype=float)))
        camera = Camera(prim_path="/genie/head_link3/head_front_Camera", resolution=(640, 400))
        world.reset()
        names = runpy.run_path(str(repo / "source/geniesim/utils/name_utils.py"))["ROBOT_CONFIGS"]["G2_omnipicker"]
        states = runpy.run_path(str(repo / "source/geniesim/benchmark/config/robot_init_states.py"))["G2_DEFAULT_STATES"]
        indices, values = [], []
        for group, key in (("arm_joints", "init_arm"), ("waist_joints", "body_state"),
                           ("head_joints", "head_state"), ("gripper_joints", "init_hand")):
            for name, value in zip(names[group], states[key]):
                indices.append(robot.dof_names.index(name))
                values.append(1 - value if group == "gripper_joints" else value)
        indices = np.asarray(indices)
        values = np.asarray(values)
        robot.set_joint_positions(values, joint_indices=indices)
        robot.set_joint_velocities(np.zeros(len(indices)), joint_indices=indices)
        camera.initialize()
        controller = robot.get_articulation_controller()
        controller.apply_action(ArticulationAction(joint_positions=values, joint_indices=indices))
        for _ in range(90):
            world.step(render=True)
        before = np.asarray(camera.get_rgba()[..., :3], dtype=np.uint8)
        Image.fromarray(before).save(out / "before.png")

        sys.path.insert(0, str(repo / "source/geniesim/utils"))
        from ikfk_utils import IKFKSolver

        arm = states["init_arm"]
        solver = IKFKSolver(arm, states["head_state"], states["body_state"], robot_cfg="G2_omnipicker")
        initial_eef = solver.compute_eef(arm)["left"]
        arm_base = get_current_stage().GetPrimAtPath("/genie/arm_base_link")
        if not arm_base.IsValid():
            raise RuntimeError("G2 arm_base_link missing")
        transform = UsdGeom.Xformable(arm_base).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        base_quat = transform.ExtractRotationQuat()
        base_rotation = Rotation.from_quat([*base_quat.GetImaginary(), base_quat.GetReal()])
        local_quat = np.asarray(initial_eef[4:] + initial_eef[3:4])
        world_quat = (base_rotation * Rotation.from_quat(local_quat)).as_quat()
        local_start = np.asarray(initial_eef[:3], dtype=float)
        local_target = local_start + np.asarray([0.05, 0, 0])
        start_world = transform.Transform(Gf.Vec3d(*local_start))
        target_world = transform.Transform(Gf.Vec3d(*local_target))
        plan = Plan("place_block_into_box", "left", "world", "m", "xyzw",
                    (Waypoint(Pose(tuple(start_world), tuple(world_quat)), "open"),
                     Waypoint(Pose(tuple(target_world), tuple(world_quat)), "open")),
                    "bounded_motion_probe")
        (out / "motion_plan.json").write_text(plan.to_json(), encoding="utf-8")
        # Consume the same world-frame plan schema used by model backends.
        command = plan.waypoints[1].pose
        target = np.asarray(transform.GetInverse().Transform(Gf.Vec3d(*command.position_m)))
        target_quat = (base_rotation.inv() * Rotation.from_quat(command.orientation_xyzw)).as_quat()
        if float(np.linalg.norm(target - local_target)) > 1e-6:
            raise RuntimeError("world-to-arm-base position conversion failed")
        solver.left_solver.update_target_quat(target, target_quat)
        fk_error = float("inf")
        for _ in range(200):
            left = solver.left_solver.solve()
            eef = solver.compute_eef(list(left) + list(arm[7:]))["left"]
            fk_error = float(np.linalg.norm(np.asarray(eef[:3]) - target))
            if fk_error <= 0.005:
                break
        if fk_error > 0.005:
            raise RuntimeError(f"IK target error {fk_error:.6f} m")
        if float(np.max(np.abs(np.asarray(left) - np.asarray(arm[:7])))) > 0.3:
            raise RuntimeError("IK joint delta exceeds 0.3 rad")

        left_indices = np.asarray([robot.dof_names.index(name) for name in names["arm_joints"][:7]])
        controller.apply_action(ArticulationAction(joint_positions=np.asarray(left),
                                                    joint_indices=left_indices))
        for _ in range(120):
            world.step(render=True)
        actual = robot.get_joint_positions(joint_indices=left_indices)
        joint_error = float(np.max(np.abs(actual - left)))
        final_eef = solver.compute_eef(list(actual) + list(arm[7:]))["left"]
        displacement = float(np.linalg.norm(np.asarray(final_eef[:3]) - np.asarray(initial_eef[:3])))
        after = np.asarray(camera.get_rgba()[..., :3], dtype=np.uint8)
        Image.fromarray(after).save(out / "after.png")
        if joint_error > 0.02 or displacement < 0.03:
            raise RuntimeError(f"motion not reached: joint error={joint_error:.5f}, motion={displacement:.5f}")
        result = {"status": "g2_left_arm_motion_probe_passed", "robot_moved_in_simulation": True,
                  "consumed_plan_schema": "geniesim-g2-plan/1", "plan_source_method": plan.source_method,
                  "motion_command_arm_base_m": [0.05, 0, 0], "observed_eef_displacement_m": displacement,
                  "max_joint_target_error_rad": joint_error, "ik_fk_target_error_m": fk_error,
                  "policy_executed": False, "pick_place_success": None, "gpu": a.gpu}
        (out / "motion_probe.json").write_text(json.dumps(result, indent=2) + "\n")
        print("GENIESIM_G2_MOTION_PROBE_OK", json.dumps(result), flush=True)
        return 0
    finally:
        app.close()


if __name__ == "__main__":
    raise SystemExit(main())
