"""Inspect fixed G2 task ground truth inside Isaac Sim without moving the robot.

The output is diagnostic-only privileged state. It must not be presented as a
camera-derived policy observation or as a task-success result.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import runpy
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--gpu", type=int, default=4)
    parser.add_argument("--execute-approach", action="store_true",
                        help="move only to a clearance waypoint above the target")
    parser.add_argument("--plan-path", type=Path,
                        help="validated external plan; only its first clearance stage may run")
    parser.add_argument("--execute-grasp", action="store_true",
                        help="run the model's approach, close and lift stages only")
    parser.add_argument("--execute-place", action="store_true",
                        help="continue through model transfer and release if pickup succeeds")
    args = parser.parse_args()
    if args.execute_place:
        args.execute_grasp = True
    root = args.server_root.resolve()
    output_dir = args.output_dir.resolve()
    allowed = Path("/home/data_ssd1/pyj").resolve()
    if not root.is_relative_to(allowed) or not output_dir.is_relative_to(root):
        parser.error("all paths must stay under /home/data_ssd1/pyj")
    if args.plan_path is not None and not args.plan_path.resolve().is_relative_to(root):
        parser.error("plan path must stay under the server root")
    if args.execute_grasp and args.plan_path is None:
        parser.error("grasp probe requires a validated external plan")
    output_dir.mkdir(parents=True, exist_ok=True)

    from isaacsim import SimulationApp

    app = SimulationApp({"headless": True, "active_gpu": args.gpu,
                         "physics_gpu": args.gpu, "multi_gpu": False,
                         "renderer": "RayTracedLighting", "width": 640, "height": 400})
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

        upstream = root / "upstream"
        assets = upstream / "source/geniesim/assets"
        layout = upstream / "source/geniesim/benchmark/config/llm_task/place_block_into_box/0"
        selection = json.loads((root / "configs/scene_selection.json").read_text())
        world = World(stage_units_in_meters=1, physics_dt=1 / 120, rendering_dt=1 / 30)
        add_reference_to_stage(str(assets / "background/room/room_1/background.usda"), "/World")
        add_reference_to_stage(str(layout / "scene.usda"), "/World")
        add_reference_to_stage(str(assets / "robot/G2_omnipicker/robot_fix.usda"), "/genie")
        robot = world.scene.add(SingleArticulation(
            prim_path="/genie", name="G2_omnipicker",
            position=np.asarray(selection["robot_position"], dtype=float),
            orientation=np.asarray(selection["robot_quaternion_wxyz"], dtype=float)))
        camera = Camera(prim_path=selection["head_camera"], resolution=(640, 400))
        world.reset()
        names = runpy.run_path(str(upstream / "source/geniesim/utils/name_utils.py"))["ROBOT_CONFIGS"]["G2_omnipicker"]
        states = runpy.run_path(str(upstream / "source/geniesim/benchmark/config/robot_init_states.py"))["G2_DEFAULT_STATES"]
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
        robot.get_articulation_controller().apply_action(
            ArticulationAction(joint_positions=values, joint_indices=indices))
        for _ in range(90):
            world.step(render=True)

        stage = get_current_stage()
        bbox_cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_,
                                                                 UsdGeom.Tokens.render,
                                                                 UsdGeom.Tokens.proxy])

        def ground_truth(prim_path: str, include_bbox: bool = True) -> dict:
            prim = stage.GetPrimAtPath(prim_path)
            if not prim.IsValid():
                raise RuntimeError(f"missing prim: {prim_path}")
            transform = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
            center = transform.ExtractTranslation()
            data = {"prim_path": prim_path,
                    "origin_world_m": [float(v) for v in center]}
            if include_bbox:
                bbox_cache.Clear()
                extent = bbox_cache.ComputeWorldBound(prim).ComputeAlignedRange()
                lower, upper = extent.GetMin(), extent.GetMax()
                data["aabb_min_m"] = [float(v) for v in lower]
                data["aabb_max_m"] = [float(v) for v in upper]
            return data

        box_id = "benchmark_building_blocks_0f256c95"
        target_id = "benchmark_building_blocks_e4e8268e"
        base_prim = stage.GetPrimAtPath("/genie/arm_base_link")
        base_transform = UsdGeom.Xformable(base_prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        sys.path.insert(0, str(upstream / "source/geniesim/utils"))
        from ikfk_utils import IKFKSolver
        arm = list(robot.get_joint_positions(joint_indices=np.asarray(
            [robot.dof_names.index(n) for n in names["arm_joints"]])))
        solver = IKFKSolver(arm, states["head_state"], states["body_state"], robot_cfg="G2_omnipicker")
        eef_local = solver.compute_eef(arm)["left"]
        eef_world = base_transform.Transform(Gf.Vec3d(*eef_local[:3]))
        gripper_names = names["gripper_joints"]
        gripper_indices = np.asarray([robot.dof_names.index(n) for n in gripper_names])
        target_truth = ground_truth(f"/World/Objects/{target_id}")
        box_truth = ground_truth(f"/World/Objects/{box_id}")
        gripper_truth = ground_truth("/genie/gripper_l_center_link", include_bbox=False)
        target_center = (np.asarray(target_truth["aabb_min_m"]) +
                         np.asarray(target_truth["aabb_max_m"])) / 2
        box_center = (np.asarray(box_truth["aabb_min_m"]) +
                      np.asarray(box_truth["aabb_max_m"])) / 2
        gripper_center = np.asarray(gripper_truth["origin_world_m"])
        start_eef_world = np.asarray(eef_world, dtype=float)
        external_plan = (Plan.from_dict(json.loads(args.plan_path.read_text(encoding="utf-8")))
                         if args.plan_path is not None else None)
        candidate_gripper_centers = {
            "above_target": [target_center[0], target_center[1],
                             target_truth["aabb_max_m"][2] + 0.12],
            "pregrasp_target": [target_center[0], target_center[1],
                                target_truth["aabb_max_m"][2] + 0.06],
            "near_target": [target_center[0], target_center[1],
                            target_truth["aabb_max_m"][2] + 0.02],
            "contact_target": target_center.tolist(),
            "above_container": [box_center[0], box_center[1],
                                 box_truth["aabb_max_m"][2] + 0.15],
        }
        if args.execute_place:
            if external_plan is None or len(external_plan.waypoints) < 8:
                raise ValueError("placement probe requires eight model waypoints")
            for label, waypoint_index in (("model_transfer", 4), ("model_place", 5),
                                          ("model_retreat", 7)):
                candidate_gripper_centers[label] = (
                    np.asarray(external_plan.waypoints[waypoint_index].pose.position_m) +
                    gripper_center - start_eef_world).tolist()
        ik_preflight = {}
        ik_joint_solutions = {}
        initial_left = np.asarray(arm[:7], dtype=float)
        local_quat = np.asarray(eef_local[4:] + eef_local[3:4], dtype=float)
        for label, desired_gripper in candidate_gripper_centers.items():
            desired_gripper = np.asarray(desired_gripper, dtype=float)
            target_eef_world = start_eef_world + desired_gripper - gripper_center
            target_eef_local = np.asarray(base_transform.GetInverse().Transform(
                Gf.Vec3d(*target_eef_world)))
            solver.left_solver.update_target_quat(target_eef_local, local_quat)
            fk_error = float("inf")
            for iteration in range(1, 201):
                left = solver.left_solver.solve()
                reached = solver.compute_eef(list(left) + list(arm[7:]))["left"]
                fk_error = float(np.linalg.norm(np.asarray(reached[:3]) - target_eef_local))
                if fk_error <= 0.005:
                    break
            ik_preflight[label] = {
                "desired_gripper_center_world_m": desired_gripper.tolist(),
                "target_eef_world_m": target_eef_world.tolist(),
                "ik_fk_error_m": fk_error,
                "ik_calls": iteration,
                "max_joint_delta_from_initial_rad": float(np.max(np.abs(np.asarray(left) - initial_left))),
                "reachable_at_5mm": fk_error <= 0.005,
            }
            ik_joint_solutions[label] = np.asarray(left, dtype=float).copy()
        result = {
            "task": "place_block_into_box", "layout": 0, "arm": "left", "gpu": args.gpu,
            "source": "Isaac Sim privileged USD and articulation state after 90 frames",
            "policy_input": False, "robot_moved_by_policy": False, "task_success": None,
            "robot_moved_by_model_plan": bool(args.plan_path and
                                               (args.execute_approach or args.execute_grasp)),
            "target": target_truth,
            "container": box_truth,
            "left_gripper_center": gripper_truth,
            "left_eef_fk_world_m": [float(v) for v in eef_world],
            "left_eef_fk_arm_base_m": [float(v) for v in eef_local[:3]],
            "left_gripper_joint_names": gripper_names[:1],
            "left_gripper_joint_positions": [float(v) for v in robot.get_joint_positions(
                joint_indices=gripper_indices[:1])],
            "candidate_ik_preflight": ik_preflight,
            "preflight_limit": "IK/FK position only; no collision or contact validation",
        }
        Image.fromarray(np.asarray(camera.get_rgba()[..., :3], dtype=np.uint8)).save(
            output_dir / "privileged_scene.png")
        if args.execute_approach or args.execute_grasp:
            approach = ik_preflight["above_target"]
            if not approach["reachable_at_5mm"] or approach["max_joint_delta_from_initial_rad"] > 0.35:
                raise RuntimeError("clearance waypoint failed IK or joint-delta gate")
            base_quat = base_transform.ExtractRotationQuat()
            base_rotation = Rotation.from_quat([*base_quat.GetImaginary(), base_quat.GetReal()])
            world_quat = (base_rotation * Rotation.from_quat(local_quat)).as_quat()
            if args.plan_path is None:
                plan = Plan("place_block_into_box", "left", "world", "m", "xyzw", (
                    Waypoint(Pose(tuple(start_eef_world), tuple(world_quat)), "open"),
                    Waypoint(Pose(tuple(approach["target_eef_world_m"]), tuple(world_quat)), "open"),
                ), "privileged_debug_approach")
                run_name = "privileged_approach"
            else:
                plan = external_plan
                run_name = "model_approach"
                if plan.source_method != "lmtg_structured" or len(plan.waypoints) < 2:
                    raise ValueError("external plan must be an LMTG structured staged plan")
                if plan.waypoints[0].gripper != "open" or plan.waypoints[1].gripper != "open":
                    raise ValueError("first two waypoints must keep the gripper open")
                if np.linalg.norm(np.asarray(plan.waypoints[0].pose.position_m) - start_eef_world) > 0.01:
                    raise ValueError("model plan does not start at the measured end-effector pose")
                if np.linalg.norm(np.asarray(plan.waypoints[1].pose.position_m) -
                                  np.asarray(approach["target_eef_world_m"])) > 0.01:
                    raise ValueError("model approach is not within 1 cm of the safe preflight target")
                if abs(np.dot(plan.waypoints[1].pose.orientation_xyzw, world_quat)) < 0.999:
                    raise ValueError("model approach changes the wrist orientation")
            (output_dir / f"{run_name}_plan.json").write_text(plan.to_json())
            command = plan.waypoints[1].pose
            commanded_gripper_center = (np.asarray(command.position_m) +
                                        gripper_center - start_eef_world)
            if commanded_gripper_center[2] - target_truth["aabb_max_m"][2] < 0.10:
                raise ValueError("model approach clearance is below 10 cm")
            target_local = np.asarray(base_transform.GetInverse().Transform(
                Gf.Vec3d(*command.position_m)))
            left = ik_joint_solutions["above_target"]
            reached = solver.compute_eef(list(left) + list(arm[7:]))["left"]
            error = float(np.linalg.norm(np.asarray(reached[:3]) - target_local))
            joint_delta = float(np.max(np.abs(np.asarray(left) - initial_left)))
            if error > 0.005 or joint_delta > 0.35:
                raise RuntimeError(f"approach solution rejected: IK={error:.4f}, delta={joint_delta:.4f}")
            result["approach_execution"] = {
                "status": "ik_ready_before_actuation",
                "plan_schema": "geniesim-g2-plan/1",
                "source_method": plan.source_method,
                "desired_gripper_center_world_m": approach["desired_gripper_center_world_m"],
                "ik_fk_error_m": error,
                "max_joint_delta_from_initial_rad": joint_delta,
                "pick_place_success": None,
            }
            approach_result = output_dir / f"{run_name}.json"
            approach_result.write_text(json.dumps(result, indent=2) + "\n")
            print("PRIVILEGED_APPROACH_STAGE ik_ready", flush=True)
            left_indices = np.asarray([robot.dof_names.index(n) for n in names["arm_joints"][:7]])
            robot.get_articulation_controller().apply_action(
                ArticulationAction(joint_positions=np.asarray(left), joint_indices=left_indices))
            print("PRIVILEGED_APPROACH_STAGE command_sent", flush=True)
            for frame in range(1, 121):
                world.step(render=True)
                if frame % 30 == 0:
                    result["approach_execution"]["last_completed_frame"] = frame
                    approach_result.write_text(json.dumps(result, indent=2) + "\n")
                    print("PRIVILEGED_APPROACH_STAGE frame", frame, flush=True)
            actual_left = robot.get_joint_positions(joint_indices=left_indices)
            final_gripper = ground_truth("/genie/gripper_l_center_link", include_bbox=False)
            final_target = ground_truth(f"/World/Objects/{target_id}")
            object_shift = float(np.linalg.norm(
                np.asarray(final_target["origin_world_m"]) -
                np.asarray(target_truth["origin_world_m"])))
            Image.fromarray(np.asarray(camera.get_rgba()[..., :3], dtype=np.uint8)).save(
                output_dir / f"{run_name}_after.png")
            result["approach_execution"] = {
                "status": "measurement_complete",
                "plan_schema": "geniesim-g2-plan/1",
                "source_method": plan.source_method,
                "robot_moved": True,
                "grasp_attempted": False,
                "desired_gripper_center_world_m": commanded_gripper_center.tolist(),
                "actual_gripper_center_world_m": final_gripper["origin_world_m"],
                "gripper_target_error_m": float(np.linalg.norm(
                    np.asarray(final_gripper["origin_world_m"]) - commanded_gripper_center)),
                "max_joint_target_error_rad": float(np.max(np.abs(actual_left - left))),
                "target_object_origin_shift_m": object_shift,
                "clearance_above_target_bbox_m": (
                    final_gripper["origin_world_m"][2] - target_truth["aabb_max_m"][2]),
                "pick_place_success": None,
                "model_plan_consumed": args.plan_path is not None,
            }
            approach_result.write_text(json.dumps(result, indent=2) + "\n")
            if args.execute_grasp:
                if (len(plan.waypoints) < 4 or plan.waypoints[2].gripper != "closed"
                        or plan.waypoints[3].gripper != "holding"):
                    raise ValueError("model plan has no valid grasp and lift stages")
                contact = ik_preflight["contact_target"]
                if not contact["reachable_at_5mm"] or contact["max_joint_delta_from_initial_rad"] > 1.2:
                    raise ValueError("contact target failed the IK/joint-delta gate")
                if np.linalg.norm(np.asarray(plan.waypoints[2].pose.position_m) -
                                  np.asarray(contact["target_eef_world_m"])) > 0.01:
                    raise ValueError("model contact pose differs from privileged preflight by over 1 cm")
                if np.linalg.norm(np.asarray(plan.waypoints[3].pose.position_m) -
                                  np.asarray(approach["target_eef_world_m"])) > 0.01:
                    raise ValueError("model lift pose differs from the clearance waypoint")
                grasp_result = output_dir / "model_grasp.json"
                result["grasp_execution"] = {"status": "approach_complete", "privileged_debug": True,
                                             "official_pickup_test": "object rise > 0.02 m and distance < 0.1 m",
                                             "pick_place_success": None}
                grasp_result.write_text(json.dumps(result, indent=2) + "\n")
                print("MODEL_GRASP_STAGE approach_complete", flush=True)
                contact_joints = ik_joint_solutions["contact_target"]
                robot.get_articulation_controller().apply_action(
                    ArticulationAction(joint_positions=contact_joints, joint_indices=left_indices))
                for _ in range(120):
                    world.step(render=True)
                contact_gripper = ground_truth("/genie/gripper_l_center_link", include_bbox=False)
                contact_object = ground_truth(f"/World/Objects/{target_id}")
                Image.fromarray(np.asarray(camera.get_rgba()[..., :3], dtype=np.uint8)).save(
                    output_dir / "model_grasp_at_contact.png")
                result["grasp_execution"].update({
                    "status": "contact_pose_reached",
                    "contact_gripper_center_world_m": contact_gripper["origin_world_m"],
                    "contact_target_origin_world_m": contact_object["origin_world_m"],
                    "contact_joint_error_rad": float(np.max(np.abs(
                        robot.get_joint_positions(joint_indices=left_indices) - contact_joints))),
                })
                grasp_result.write_text(json.dumps(result, indent=2) + "\n")
                print("MODEL_GRASP_STAGE contact_pose_reached", flush=True)
                robot.get_articulation_controller().apply_action(
                    ArticulationAction(joint_positions=np.asarray([0.0]),
                                       joint_indices=gripper_indices[:1]))
                for _ in range(90):
                    world.step(render=True)
                result["grasp_execution"]["closed_gripper_joint_rad"] = float(
                    robot.get_joint_positions(joint_indices=gripper_indices[:1])[0])
                result["grasp_execution"]["status"] = "gripper_closed"
                grasp_result.write_text(json.dumps(result, indent=2) + "\n")
                print("MODEL_GRASP_STAGE gripper_closed", flush=True)
                lift_joints = ik_joint_solutions["above_target"]
                robot.get_articulation_controller().apply_action(
                    ArticulationAction(joint_positions=lift_joints, joint_indices=left_indices))
                for _ in range(120):
                    world.step(render=True)
                lifted_gripper = ground_truth("/genie/gripper_l_center_link", include_bbox=False)
                lifted_object = ground_truth(f"/World/Objects/{target_id}")
                lifted_box_center = (np.asarray(lifted_object["aabb_min_m"]) +
                                     np.asarray(lifted_object["aabb_max_m"])) / 2
                rise = float(lifted_box_center[2] - target_center[2])
                distance = float(np.linalg.norm(np.asarray(
                    lifted_gripper["origin_world_m"]) - lifted_box_center))
                pickup = rise > 0.02 and distance < 0.1
                Image.fromarray(np.asarray(camera.get_rgba()[..., :3], dtype=np.uint8)).save(
                    output_dir / "model_grasp_after_lift.png")
                result["grasp_execution"].update({
                    "status": "pickup_observed" if pickup else "pickup_failed_stop_before_transfer",
                    "lifted_gripper_center_world_m": lifted_gripper["origin_world_m"],
                    "lifted_target_origin_world_m": lifted_object["origin_world_m"],
                    "lifted_target_bbox_center_world_m": lifted_box_center.tolist(),
                    "target_rise_m": rise,
                    "usd_root_origin_remained_static": (
                        lifted_object["origin_world_m"] == target_truth["origin_world_m"]),
                    "gripper_to_target_bbox_center_m": distance,
                    "official_pickup_threshold_passed": pickup,
                    "grasp_attempted": True,
                    "transfer_attempted": False,
                    "pick_place_success": None,
                })
                grasp_result.write_text(json.dumps(result, indent=2) + "\n")
                print("MODEL_GRASP_STAGE", result["grasp_execution"]["status"], flush=True)
                if args.execute_place and pickup:
                    result["grasp_execution"]["transfer_attempted"] = True
                    expected_grippers = ["holding", "holding", "open", "open"]
                    if [w.gripper for w in plan.waypoints[4:8]] != expected_grippers:
                        raise ValueError("model transfer/release gripper sequence is invalid")
                    for label in ("model_transfer", "model_place", "model_retreat"):
                        candidate = ik_preflight[label]
                        if not candidate["reachable_at_5mm"] or candidate[
                                "max_joint_delta_from_initial_rad"] > 1.5:
                            raise ValueError(f"{label} failed the IK/joint-delta gate")
                    place_result = output_dir / "model_place.json"
                    result["place_execution"] = {"status": "pickup_passed_transfer_pending",
                                                 "official_task_evaluator_ran": False,
                                                 "pick_place_success": None}
                    place_result.write_text(json.dumps(result, indent=2) + "\n")
                    print("MODEL_PLACE_STAGE pickup_passed", flush=True)

                    transfer_joints = ik_joint_solutions["model_transfer"]
                    robot.get_articulation_controller().apply_action(
                        ArticulationAction(joint_positions=transfer_joints,
                                           joint_indices=left_indices))
                    for _ in range(180):
                        world.step(render=True)
                    transfer_gripper = ground_truth("/genie/gripper_l_center_link", include_bbox=False)
                    transfer_object = ground_truth(f"/World/Objects/{target_id}")
                    transfer_center = (np.asarray(transfer_object["aabb_min_m"]) +
                                       np.asarray(transfer_object["aabb_max_m"])) / 2
                    transfer_distance = float(np.linalg.norm(np.asarray(
                        transfer_gripper["origin_world_m"]) - transfer_center))
                    carried = (transfer_center[2] - target_center[2] > 0.02
                               and transfer_distance < 0.1)
                    Image.fromarray(np.asarray(camera.get_rgba()[..., :3], dtype=np.uint8)).save(
                        output_dir / "model_place_after_transfer.png")
                    result["place_execution"].update({
                        "status": "transfer_carried" if carried else "dropped_during_transfer",
                        "transfer_target_bbox_center_world_m": transfer_center.tolist(),
                        "transfer_gripper_center_world_m": transfer_gripper["origin_world_m"],
                        "transfer_gripper_to_object_m": transfer_distance,
                        "transfer_joint_error_rad": float(np.max(np.abs(
                            robot.get_joint_positions(joint_indices=left_indices) - transfer_joints))),
                    })
                    place_result.write_text(json.dumps(result, indent=2) + "\n")
                    print("MODEL_PLACE_STAGE", result["place_execution"]["status"], flush=True)
                    if carried:
                        place_joints = ik_joint_solutions["model_place"]
                        robot.get_articulation_controller().apply_action(
                            ArticulationAction(joint_positions=place_joints,
                                               joint_indices=left_indices))
                        for _ in range(120):
                            world.step(render=True)
                        Image.fromarray(np.asarray(camera.get_rgba()[..., :3], dtype=np.uint8)).save(
                            output_dir / "model_place_before_release.png")
                        result["place_execution"]["status"] = "place_pose_reached"
                        place_result.write_text(json.dumps(result, indent=2) + "\n")
                        print("MODEL_PLACE_STAGE place_pose_reached", flush=True)
                        robot.get_articulation_controller().apply_action(
                            ArticulationAction(joint_positions=np.asarray([1.0]),
                                               joint_indices=gripper_indices[:1]))
                        for _ in range(90):
                            world.step(render=True)
                        result["place_execution"]["open_gripper_joint_rad"] = float(
                            robot.get_joint_positions(joint_indices=gripper_indices[:1])[0])
                        result["place_execution"]["status"] = "gripper_released"
                        place_result.write_text(json.dumps(result, indent=2) + "\n")
                        print("MODEL_PLACE_STAGE gripper_released", flush=True)
                        retreat_joints = ik_joint_solutions["model_retreat"]
                        robot.get_articulation_controller().apply_action(
                            ArticulationAction(joint_positions=retreat_joints,
                                               joint_indices=left_indices))
                        for _ in range(120):
                            world.step(render=True)
                        final_object = ground_truth(f"/World/Objects/{target_id}")
                        final_center = (np.asarray(final_object["aabb_min_m"]) +
                                        np.asarray(final_object["aabb_max_m"])) / 2
                        final_box = ground_truth(f"/World/Objects/{box_id}")
                        box_low = np.asarray(final_box["aabb_min_m"])
                        box_high = np.asarray(final_box["aabb_max_m"])
                        box_middle = (box_low + box_high) / 2
                        scaled_low = box_middle - 0.4 * (box_high - box_low)
                        scaled_high = box_middle + 0.4 * (box_high - box_low)
                        inside_proxy = bool(np.all(final_center >= scaled_low) and
                                            np.all(final_center <= scaled_high))
                        Image.fromarray(np.asarray(camera.get_rgba()[..., :3], dtype=np.uint8)).save(
                            output_dir / "model_place_after_retreat.png")
                        result["place_execution"].update({
                            "status": "release_inside_outer_box_aabb_proxy" if inside_proxy
                                      else "release_outside_outer_box_aabb_proxy",
                            "final_target_bbox_center_world_m": final_center.tolist(),
                            "final_container_aabb_min_m": box_low.tolist(),
                            "final_container_aabb_max_m": box_high.tolist(),
                            "inside_0_8_outer_box_aabb_proxy": inside_proxy,
                            "proxy_limit": "outer AABB is not hole geometry or the full official evaluator",
                            "official_task_evaluator_ran": False,
                            "pick_place_success": None,
                        })
                        place_result.write_text(json.dumps(result, indent=2) + "\n")
                        print("MODEL_PLACE_STAGE", result["place_execution"]["status"], flush=True)
        (output_dir / "privileged_scene.json").write_text(json.dumps(result, indent=2) + "\n")
        print("GENIESIM_PRIVILEGED_SCENE_OK", json.dumps(result), flush=True)
        return 0
    finally:
        app.close()


if __name__ == "__main__":
    raise SystemExit(main())
