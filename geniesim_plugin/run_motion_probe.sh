#!/usr/bin/env bash
set -euo pipefail
ROOT=/home/data_ssd1/pyj/GenieSimG2
PLUGIN="$ROOT/plugins/language-models-trajectory-generators"
export HOME="$ROOT/cache/home"
export XDG_CACHE_HOME="$ROOT/cache/xdg/cache"
export XDG_CONFIG_HOME="$ROOT/cache/xdg/config"
export XDG_DATA_HOME="$ROOT/cache/xdg/data"
export OMNI_USER_DIR="$ROOT/cache/omni/user"
export OMNI_KIT_CACHE_DIR="$ROOT/cache/omni/kit"
export CUDA_CACHE_PATH="$ROOT/cache/cuda"
export TMPDIR="$ROOT/cache/tmp"
export PYTHONDONTWRITEBYTECODE=1
export OMNI_KIT_ACCEPT_EULA=YES
export LD_LIBRARY_PATH="$ROOT/deps/tinyxml/extracted/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
mkdir -p "$HOME" "$XDG_CACHE_HOME" "$XDG_CONFIG_HOME" "$XDG_DATA_HOME" \
  "$OMNI_USER_DIR" "$OMNI_KIT_CACHE_DIR" "$CUDA_CACHE_PATH" "$TMPDIR" "$PLUGIN/verification"
cd "$PLUGIN"
if [[ "${GENIESIM_PROBE_MODE:-motion}" == "privileged-scene" ]]; then
  "$ROOT/.venv/bin/python" -m geniesim_plugin.probe_privileged_scene \
    --server-root "$ROOT" --output-dir "$PLUGIN/verification" "$@" \
    > "$PLUGIN/verification/privileged_scene.log" 2>&1
  cat "$PLUGIN/verification/privileged_scene.json"
elif [[ "${GENIESIM_PROBE_MODE:-motion}" == "privileged-approach" ]]; then
  "$ROOT/.venv/bin/python" -m geniesim_plugin.probe_privileged_scene \
    --server-root "$ROOT" --output-dir "$PLUGIN/verification" --execute-approach "$@" \
    > "$PLUGIN/verification/privileged_approach.log" 2>&1
  cat "$PLUGIN/verification/privileged_approach.json"
elif [[ "${GENIESIM_PROBE_MODE:-motion}" == "model-approach" ]]; then
  "$ROOT/.venv/bin/python" -m geniesim_plugin.probe_privileged_scene \
    --server-root "$ROOT" --output-dir "$PLUGIN/verification" --execute-approach \
    --plan-path "$PLUGIN/verification/deepseek_g2_debug_plan.json" "$@" \
    > "$PLUGIN/verification/model_approach.log" 2>&1
  cat "$PLUGIN/verification/model_approach.json"
elif [[ "${GENIESIM_PROBE_MODE:-motion}" == "model-grasp" ]]; then
  "$ROOT/.venv/bin/python" -m geniesim_plugin.probe_privileged_scene \
    --server-root "$ROOT" --output-dir "$PLUGIN/verification" --execute-grasp \
    --plan-path "$PLUGIN/verification/deepseek_g2_debug_plan.json" "$@" \
    > "$PLUGIN/verification/model_grasp.log" 2>&1
  cat "$PLUGIN/verification/model_grasp.json"
elif [[ "${GENIESIM_PROBE_MODE:-motion}" == "model-place" ]]; then
  "$ROOT/.venv/bin/python" -m geniesim_plugin.probe_privileged_scene \
    --server-root "$ROOT" --output-dir "$PLUGIN/verification" --execute-place \
    --plan-path "$PLUGIN/verification/deepseek_g2_debug_plan.json" "$@" \
    > "$PLUGIN/verification/model_place.log" 2>&1
  cat "$PLUGIN/verification/model_place.json"
else
  "$ROOT/.venv/bin/python" -m geniesim_plugin.probe_g2_motion \
    --server-root "$ROOT" --output-dir "$PLUGIN/verification" "$@" \
    > "$PLUGIN/verification/motion_probe.log" 2>&1
  cat "$PLUGIN/verification/motion_probe.json"
fi
