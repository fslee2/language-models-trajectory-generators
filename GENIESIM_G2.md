# GenieSim G2 planning adapter

This is a standalone, standard-library Python 3.11 package inside the upstream
Language Models as Trajectory Generators repository. It adapts that project's
staged end-effector trajectory planning idea and prompt into structured JSON.
The upstream repository is MIT licensed; see [LICENSE](LICENSE). The adapter
does not import or change `main.py` and does not execute model-generated code.

## Plan contract

`geniesim_plugin.schema` is the canonical boundary for both planning methods.
Plans identify the `place_block_into_box` task and left arm, and declare
positions in metres in the GenieSim scene world frame. Orientation is a
normalized Hamilton quaternion in **xyzw** order. Every waypoint also carries a
gripper state (`open`, `closed`, or `holding`). Values must be finite, position
components are bounded to ±2 m, and a plan has at most 32 waypoints. All plans
remain marked `proposed_unexecuted`.

`LMTGStructuredMethod` takes an injectable callable or client with a
`complete(prompt)` method. It accepts JSON text or a mapping and validates the
result; generated Python, tool calls, and arbitrary code are not accepted.
`ExistingWorkflowMethod` adapts externally prepared plan data to the same
schema. Neither adapter contains a robot control path.
Observations can also carry camera-frame file references and structured action
history for future VLM methods. The current LMTG text prompt receives the file
paths only, not image pixels; an image-capable method must open and transmit
those frames through its own injected client.

## Offline dry run

From this directory, run:

```powershell
python -m geniesim_plugin.cli --dry-run `
  --manifest D:/Simpler/environments/geniesim_g2/configs/verified_scene_manifest.json `
  --selection D:/Simpler/environments/geniesim_g2/configs/scene_selection.json `
  --head-image D:/Simpler/outputs/geniesim_g2/g2_place_block_layout0/head_camera.png `
  --output proposed_plan.json
```

The loader checks the pinned layout/task/left-arm selection, verifies the
official yellow target (`benchmark_building_blocks_e4e8268e`) and container
(`benchmark_building_blocks_0f256c95`) IDs and expected assets, and confirms
that the selection and verified manifest have identical object metadata. The
offline geometric draft uses center positions and nominal height offsets. It
is for inspection only: those offsets are not calibrated contact poses, the
proposal is not a validated collision-free trajectory, it does not move the
robot, and writing it does not establish task success.

## Limits

The upstream project targets PyBullet Sawyer/Franka and its compact 4-tuple
rotation convention is not assumed to map to G2. The original `main.py` also
executes model-generated Python; the G2 path accepts validated JSON instead.
It does not install the upstream PyBullet/LangSAM/XMem dependency stack into
Isaac Sim. Model providers may be injected into the planning interface later;
no model API request is made by the offline tests.

## Bounded G2 control probe on the server

The pinned GenieSim repo bundles its G2 `ik_solver` wheel. On the server, run
these scripts from this plugin after the existing G2 scene has been set up:

```bash
ROOT=/home/data_ssd1/pyj/GenieSimG2
bash "$ROOT/plugins/language-models-trajectory-generators/geniesim_plugin/setup_ik.sh"
bash "$ROOT/plugins/language-models-trajectory-generators/geniesim_plugin/run_ik_probe.sh"
bash "$ROOT/plugins/language-models-trajectory-generators/geniesim_plugin/run_motion_probe.sh"
```

`setup_ik.sh` installs only into the isolated environment and unpacks the
needed TinyXML runtime below `ROOT/deps/`; it does not change system packages.
The IK probe checks a five-centimetre left-end-effector target via the official
G2 solver, FK and the world/arm-base transform. The motion probe loads the
official scene, creates a validated two-waypoint plan, converts its world-frame
pose to the arm-base frame, solves IK, commands the left arm and verifies its
measured joint positions and FK displacement. Results and head-camera before/
after images are in `verification/`; images and logs are excluded from Git.

This only establishes that a bounded plan waypoint can be executed in Isaac
Sim. It does not execute an LMTG or VLM-generated pick/place plan, command the
gripper, use collision checks, run the official benchmark evaluator, or claim
task success. The offline geometric draft is not suitable for execution.

Run the standard-library tests with `python -m unittest discover -s tests`.

## First oracle-assisted DeepSeek rollout

The local `geniesim_plugin.run_deepseek_debug_plan` entry point accepts a
privileged scene snapshot, keeps the API key on the workstation, and emits a
validated eight-waypoint `lmtg_structured` plan. The server probe reads only
that JSON plan; it now covers staged approach, grasp, lift, transfer, release,
and retreat in the pinned G2 Isaac scene. This is a debugging path with object
AABBs and robot ground truth supplied to the model, not a visual policy score.
The first full run picked up and carried the yellow block, then left it on the
box lid rather than in the round hole. Details, measurements and the official
evaluator limit are in `GENIESIM_MODEL_DEBUG_20260930.md`.
