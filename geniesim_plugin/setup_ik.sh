#!/usr/bin/env bash
set -euo pipefail
ROOT=/home/data_ssd1/pyj/GenieSimG2
DEPS="$ROOT/deps/tinyxml"
mkdir -p "$DEPS" "$ROOT/cache/uv" "$ROOT/cache/tmp"
export UV_CACHE_DIR="$ROOT/cache/uv"
export TMPDIR="$ROOT/cache/tmp"
uv pip install --python "$ROOT/.venv/bin/python" \
  "$ROOT/upstream/3rdparty/ik_solver-0.4.3-cp311-cp311-linux_x86_64.whl"
if [ ! -f "$DEPS/extracted/usr/lib/x86_64-linux-gnu/libtinyxml.so.2.6.2" ]; then
  (cd "$DEPS" && apt download libtinyxml2.6.2v5 && \
    dpkg-deb -x libtinyxml2.6.2v5_*.deb extracted)
fi
