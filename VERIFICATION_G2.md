# G2 adapter verification · 2026-09-30

Source isolation: this directory is an independent clone of
`kwonathan/language-models-trajectory-generators` at
`4385a762b523eed429b1d0418b8e1403a310fbf7`. All added G2 control code,
tests, dashboard source and skill source live in this repository. The parent
`D:/Simpler` repository and the pinned GenieSim upstream source were not edited.

The original LMTG implementation runs in PyBullet with Sawyer or Franka,
assumes a four-value xyz+yaw end-effector pose, and executes generated Python.
The isolated G2 adapter uses a typed JSON plan in world metres with xyzw
quaternions and an injectable planning method. It does not import or execute
upstream `main.py`. `ExistingWorkflowMethod` and `LMTGStructuredMethod` use the
same plan contract. The current offline observation comes from the fixed scene
manifest (ground truth), not from a VLM or live camera perception.

Local checks: 8 standard-library tests pass; the CLI validates the actual
`place_block_into_box` layout-0 manifest and emits an unexecuted eight-waypoint
draft. The CLI also accepted the actual head-camera image path as a reference
for future VLM methods. `verification/offline_draft.json` is that draft, not a
safe grasp plan.
The installed dashboard skill and its versioned plugin copy pass
`quick_validate.py`; `dashboard/index.html` was generated from the skill and
`dashboard/state.json`.

Server runtime: all changes/outputs stayed under
`/home/data_ssd1/pyj/GenieSimG2`. The official G2 IK wheel was installed in
the existing isolated Isaac venv. Its TinyXML dependency was unpacked below
`deps/tinyxml`, without changing system packages. On A100 GPU 4, the IK probe
converted between scene-world and G2 `arm_base_link` coordinates and solved a
5 cm target with 4.98 mm FK position error after 126 short solver calls; no
robot movement occurred in that probe (`verification/ik_probe.json`).

The second probe created and consumed a `geniesim-g2-plan/1` world-frame
two-waypoint plan, converted the target to the arm-base frame, solved IK,
commanded the official G2 left-arm joints in Isaac Sim and measured 4.70 cm
end-effector displacement. Max final joint error was 2.2e-5 rad. The scene's
head camera produced visually distinct before/after frames. See
`verification/motion_plan.json` and `verification/motion_probe.json`; PNGs/logs
are kept locally on server and workstation but excluded from Git.

These probes establish a working plan-format-to-G2-motion boundary. They do
not show that an LMTG/VLM model can plan this task, that the offline draft is
collision-free, that the gripper can grasp the yellow block, or that the
official RoboColosseum evaluator reports success. Those are the next tests.
