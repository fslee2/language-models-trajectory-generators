import json
from pathlib import Path
import tempfile
import unittest

from geniesim_plugin.adapters import ExistingWorkflowMethod, LMTGStructuredMethod, propose
from geniesim_plugin.cli import main, offline_proposal
from geniesim_plugin.schema import Plan, Pose, Waypoint
from geniesim_plugin.task import CONTAINER_ID, TARGET_ID, load_observation

def valid_plan_dict(source="lmtg_structured"):
    return {
        "schema_version": "geniesim-g2-plan/1", "task": "place_block_into_box",
        "arm": "left", "frame": "world", "position_unit": "m", "quaternion_order": "xyzw",
        "waypoints": [{"pose": {"position_m": [0, 0, 1], "orientation_xyzw": [0, 0, 0, 1]},
                       "gripper": "open"}],
        "source_method": source, "status": "proposed_unexecuted",
    }


class SchemaTests(unittest.TestCase):
    def test_round_trip_is_serializable_and_declares_conventions(self):
        plan = Plan.from_dict(valid_plan_dict())
        roundtrip = Plan.from_dict(json.loads(plan.to_json()))
        self.assertEqual(roundtrip, plan)
        self.assertEqual(plan.to_dict()["quaternion_order"], "xyzw")

    def test_rejects_bad_quaternion_bounds_and_gripper(self):
        with self.assertRaises(ValueError):
            Pose((0, 0, 0), (0, 0, 0, 0))
        with self.assertRaises(ValueError):
            Pose((2.1, 0, 0), (0, 0, 0, 1))
        bad = valid_plan_dict()
        bad["waypoints"][0]["gripper"] = "maybe"
        with self.assertRaises(ValueError):
            Plan.from_dict(bad)

    def test_rejects_too_many_waypoints(self):
        data = valid_plan_dict()
        data["waypoints"] *= 33
        with self.assertRaises(ValueError):
            Plan.from_dict(data)


class PlannerTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        folder = Path(temp.name)
        self.manifest_path = folder / "verified_scene_manifest.json"
        self.selection_path = folder / "scene_selection.json"
        objects = {
            TARGET_ID: {"usd": "benchmark_building_blocks_002",
                        "xyz": [-0.087, 0.245, 0.815], "xyzw": [0, 0, 0, 1]},
            CONTAINER_ID: {"usd": "benchmark_building_blocks_000",
                           "xyz": [0.092, 0.04, 0.872], "xyzw": [0, 0, 0, 1]},
        }
        self.manifest_path.write_text(json.dumps({
            "task": "place_block_into_box", "layout": 0, "active_arm": "left",
            "instruction": "Place the yellow block in the round hole", "objects": objects,
        }))
        self.selection_path.write_text(json.dumps({
            "task": "place_block_into_box", "layout": 0, "arm": "left",
            "objects": objects,
        }))
        self.observation = load_observation(self.manifest_path, self.selection_path)

    def test_injected_callable_receives_observation_and_returns_plan(self):
        calls = []
        def client(prompt):
            calls.append(prompt)
            return valid_plan_dict()
        result = propose(LMTGStructuredMethod(client), self.observation)
        self.assertEqual(result.source_method, "lmtg_structured")
        self.assertEqual(len(calls), 1)
        self.assertIn(TARGET_ID, calls[0])
        self.assertIn(CONTAINER_ID, calls[0])

    def test_existing_workflow_uses_same_schema(self):
        plan = propose(ExistingWorkflowMethod(valid_plan_dict("existing_workflow")), self.observation)
        self.assertEqual(plan, Plan.from_dict(valid_plan_dict("existing_workflow")))

    def test_observation_can_carry_a_head_frame_reference(self):
        with tempfile.TemporaryDirectory() as temp:
            frame = Path(temp) / "head.png"
            frame.write_bytes(b"frame reference")
            observation = load_observation(self.manifest_path, self.selection_path, frame)
            self.assertEqual(observation.to_dict()["image_paths"]["head"], str(frame.resolve()))

    def test_manifest_validation_and_cli_dry_run(self):
        observation = self.observation
        self.assertEqual(set(observation.objects), {TARGET_ID, CONTAINER_ID})
        proposal = offline_proposal(observation)
        self.assertEqual(proposal.status, "proposed_unexecuted")
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "proposal.json"
            rc = main(["--manifest", str(self.manifest_path),
                       "--selection", str(self.selection_path),
                       "--output", str(output), "--dry-run"])
            self.assertEqual(rc, 0)
            saved = Plan.from_dict(json.loads(output.read_text(encoding="utf-8")))
            self.assertEqual(saved.source_method, "offline_geometry_draft")

    def test_manifest_rejects_object_selection_mismatch(self):
        with tempfile.TemporaryDirectory() as temp:
            selection = json.loads(self.selection_path.read_text(encoding="utf-8"))
            selection["objects"][TARGET_ID]["xyz"][0] += 0.01
            path = Path(temp) / "selection.json"
            path.write_text(json.dumps(selection), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_observation(self.manifest_path, path)


if __name__ == "__main__":
    unittest.main()
