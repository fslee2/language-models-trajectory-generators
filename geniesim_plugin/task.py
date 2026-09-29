"""Load and cross-check the pinned GenieSim scene metadata."""

from __future__ import annotations

import json
from pathlib import Path

from .schema import Observation, Pose

TARGET_ID = "benchmark_building_blocks_e4e8268e"
CONTAINER_ID = "benchmark_building_blocks_0f256c95"


def load_observation(manifest_path: str | Path, selection_path: str | Path,
                     head_image: str | Path | None = None) -> Observation:
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    selection = json.loads(Path(selection_path).read_text(encoding="utf-8"))
    for source, name in ((manifest, "manifest"), (selection, "selection")):
        if source.get("task") != "place_block_into_box" or source.get("layout") != 0:
            raise ValueError(f"{name} must select place_block_into_box layout 0")
        if source.get("active_arm", source.get("arm")) != "left":
            raise ValueError(f"{name} must select the left arm")
        objects = source.get("objects", {})
        if TARGET_ID not in objects or CONTAINER_ID not in objects:
            raise ValueError(f"{name} is missing the official target or container object id")
    if manifest["objects"][TARGET_ID]["usd"] != "benchmark_building_blocks_002":
        raise ValueError("target id no longer identifies the expected yellow block asset")
    if manifest["objects"][CONTAINER_ID]["usd"] != "benchmark_building_blocks_000":
        raise ValueError("container id no longer identifies the expected box asset")
    if selection["objects"] != manifest["objects"]:
        raise ValueError("selection object poses do not match the verified manifest")
    instruction = manifest.get("instruction")
    image_paths = {}
    if head_image is not None:
        path = Path(head_image)
        if not path.is_file():
            raise FileNotFoundError(path)
        image_paths["head"] = str(path.resolve())
    return Observation(
        task=manifest["task"], instruction=instruction, arm="left",
        objects={key: Pose(tuple(manifest["objects"][key]["xyz"]),
                           tuple(manifest["objects"][key]["xyzw"]))
                 for key in (TARGET_ID, CONTAINER_ID)},
        image_paths=image_paths,
    )
