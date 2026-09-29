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
"$ROOT/.venv/bin/python" -m geniesim_plugin.probe_g2_motion \
  --server-root "$ROOT" --output-dir "$PLUGIN/verification" "$@" \
  > "$PLUGIN/verification/motion_probe.log" 2>&1
cat "$PLUGIN/verification/motion_probe.json"
