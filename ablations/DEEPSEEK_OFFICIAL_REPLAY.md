# DeepSeek Flash on the upstream apple-in-bowl example

This is a **text and code-generation ablation**, not a PyBullet or Genie Sim success result. The upstream README calls `outputs/` "example LLM outputs"; it does not give an independently measured success flag for this transcript.

## Fixed conditions

- Upstream task: `place the apple in the bowl`, using the published GPT-4 transcript in `outputs/place_apple_in_bowl.txt`.
- Prompt: unmodified `prompts/main_prompt.py`, with the repository's configured end-effector start `[0.0, 0.6, 0.55]` and the upstream command inserted exactly as `main.py` does.
- Model: DeepSeek API `deepseek-flash`, chat completions, `temperature=0`. The `none` control had a 5,000-token cap; reasoning runs had an 8,000-token cap to allow for reasoning tokens. Neither completed `none` nor `low` response hit its cap. The API returned the same model identifier. The [provider's update log](https://api-docs.deepseek.com/updates/) identifies the current Flash alias as V4.1 Flash; the historical V4 Flash is not separately selected by this alias.
- First turn: original prompt only. Second turn: the corresponding first DeepSeek response, followed by the published apple/bowl `detect_object` printout as a user message, mirroring `main.py` and `PRINT_OUTPUT_PROMPT`.
- Generated Python was parsed with `ast` but **never executed**. No simulated robot or scene was started, and no success detector ran.
- Reproduction: `py -3 ablations/deepseek_official_replay.py first --reasoning low` then `py -3 ablations/deepseek_official_replay.py continue --reasoning low`. The local `D:/Simpler/deepseek_api_key.txt` supplies the API key. The script refuses to overwrite an existing result and never saves the key. Each phase is a paid API call.

## Results

| Condition | First turn | After published detection | Interpretation |
|---|---|---|---|
| Reasoning `low` (requested primary run) | Detects apple and bowl; 1,513 reasoning tokens, then a valid code block. | Returns one syntactically valid Python block with six 100-point, four-element-pose trajectories. Sequence: initial `open_gripper`, approach apple, descend, close, lift, approach bowl, descend, open, retreat, `task_completed`. 3,512 reasoning tokens in this turn. | Structurally consistent with the upstream task and start pose. Physical success unknown. |
| Reasoning `none` (earlier control) | Detects apple and bowl. | Nine valid code blocks with the same six-motion grasp/place sequence. | Structurally plausible, but its prose incorrectly states the bowl top is 0.092 m while its code computes 0.066 m. Physical success unknown. |
| Reasoning `high` (attempted before `low`) | Reached the 8,000-token output cap with 8,000 reasoning tokens and `finish_reason=length`; returned no user-visible code. | Not attempted because there was no detection call to replay. | Does not complete this test at the chosen cap. This is a truncation result, not a task-quality comparison. |

The `low` output uses the published apple center `[-0.07, 0.132, 0.058]` and bowl center `[0.239, 0.285, 0.04]`. It computes the bowl rim as `0.04 + 0.052 / 2 = 0.066 m` and commands release at `z=0.080 m`. It rotates the gripper to `-0.47 rad` to align with the apple's stated shorter-side orientation. All six declared trajectory endpoints chain continuously from `[0.0, 0.6, 0.55, 0.0]`; the interpolation helper returns four values per point. These are static observations of generated code, not collision or reachability measurements. The initial `open_gripper` is redundant because the original prompt says the gripper starts open, but it does not change the intended action order.

The generated plan is **structurally plausible** and closer to the prompt's geometry than the no-reasoning control in this single run. Neither DeepSeek response nor the upstream GPT-4 transcript proves a successful placement. In particular, there is no evidence yet that the gripper avoids the bowl rim, that the arm can reach each pose, or that the apple settles inside the bowl. The next experiment should test these trajectories in the original PyBullet scene with collision and final-object-pose checks before adapting the model to G2/Genie Sim.

Raw metadata, usage, responses, and AST summaries are in `ablations/results/place_apple_in_bowl_deepseek_flash_{low,none,high}.json`. The `high` file has only a first-turn response because that response was truncated.

The separate `deepseek-v4-flash` legacy-name check is documented in `ablations/DEEPSEEK_V4_ALIAS_CHECK.md`. It is a compatibility-alias check against V4.1 Flash, not a historical V4 experiment.
