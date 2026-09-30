# First DeepSeek → Genie Sim G2 debug rollout · 2026-09-30

The plugin is now connected through a bounded end-to-end path: local DeepSeek Flash (`reasoning_effort=low`) produced a validated `geniesim-g2-plan/1` JSON plan; the plan JSON alone was copied to the server; the pinned Genie Sim v3.0.3 `place_block_into_box` layout 0 scene on A100 GPU 4 consumed it and moved G2's **left** arm and gripper. This was an **oracle-assisted debug run**: the model prompt included privileged object AABBs, measured end-effector and gripper-center poses, and their offset. It received no camera pixels. The API key stayed on the workstation and was not copied to the server.

## What actually happened

| Stage | Measured evidence |
|---|---|
| Scene and frame check | Yellow target's authored USD root origin was `z=0.815 m`, while the initial visible/dynamic AABB center was about `z=0.751 m`. The IK end-effector reference and `/genie/gripper_l_center_link` differed by several centimetres. World-to-arm-base conversion and candidate IK/FK checks passed. |
| Gripper convention | Official `PiEnv.reset` commands `1 - init_hand`; its initial opened left gripper settled at about `0.785 rad`. The earlier probe had applied `init_hand=0` directly. We corrected the scene and motion probes before the model rollout. |
| Model plan | Eight validated waypoints: current pose, approach, close at the block, lift, transfer over box, descend, open, retreat. The model plan retained the measured end-effector quaternion. `status=proposed_unexecuted` describes the proposal file; actual execution is recorded separately. |
| Approach | Plan waypoint 1 reached with measured gripper-center error `0.00368 m` and clearance `0.12289 m` above the target AABB; target object did not shift. |
| Pickup | After close and lift, the **dynamic target AABB center** rose `0.13338 m` and was `0.00839 m` from the gripper center. This passes the official `PickUpOnGripper` primitive's published rise/distance thresholds (`>0.02 m`, `<0.1 m`) as a diagnostic proxy. The full official evaluator was not run. |
| Transfer | Target AABB center stayed `0.01306 m` from the gripper center over the box. |
| Release | Commanded gripper-center release height was about `0.92753 m`, around `0.05000 m` above the box outer AABB top. After retreat, target AABB center was `z=0.89637 m`, `0.01885 m` above the box top. The target was outside the 0.8-scaled outer-box AABB proxy, and the rendered frame shows it resting on the red lid beside the hole. |

The **placement failed** in this rollout. The current observation provides the box's outer AABB, not the round hole's position and free interior clearance; the model selected the outer-box center and released above the lid. We should measure or infer the round-hole pose and verify the grasped object's approach and release geometry before another placement attempt. The actual RoboColyseum/Genie evaluator did **not** run, so no official benchmark score or success rate is claimed.

An initial diagnostic wrongly labelled the grasp a failure because it measured rise from the authored USD root transform, which stayed at its original value under PhysX. The dynamic world AABB and the rendered image showed the object moving with the gripper. The corrected script uses dynamic AABB centers for grasp and placement diagnostics; the final complete rollout contains the corrected measurement.

## Artifacts and limits

- Local reproducible code: `geniesim_plugin/run_deepseek_debug_plan.py`, `geniesim_plugin/probe_privileged_scene.py`, and `geniesim_plugin/run_motion_probe.sh`.
- Key-free plan and model metadata: `verification/deepseek_g2_debug_plan.json` and `verification/deepseek_g2_debug_plan.response.json`.
- Privileged scene and approach measurements: `verification/privileged_scene.json`, `verification/privileged_approach.json`, `verification/model_grasp.json`, and `verification/model_place.json`.
- Stage PNGs remain local (not in Git): `verification/model_grasp_after_lift.png`, `verification/model_place_after_transfer.png`, `verification/model_place_before_release.png`, and `verification/model_place_after_retreat.png`.
- The loop used Isaac Sim native scene loading and control with the pinned Genie assets. It did not instantiate the full official benchmark policy/evaluator runtime; the threshold and outer-AABB checks above are diagnostic approximations.

The next run should obtain the actual circular-hole target from geometry or perception, lower/release relative to that target, and then invoke the official `Follow → PickUpOnGripper → Inside` evaluation chain. A separate non-privileged run is needed before claiming model perception or task generalization.
