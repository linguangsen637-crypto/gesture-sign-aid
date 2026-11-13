"""Index the published pick_cup ACT policy and keep motor commands explicit."""

import argparse
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from gesture_aid.contracts import Intent, RetrievalRequest, Status
from gesture_aid.robot.act import ActRobot, rollout_argv, validate_policy_config
from gesture_aid.robot.cli import add_command, run
from gesture_aid.robot.skills import load_skills
from gesture_aid.workflow.controller import RetrievalWorkflow

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "configs" / "skills.example.json"
FIXTURE = Path(__file__).parent / "fixtures" / "act_cupfinal_config.json"
POLICY = "axellin/act_cupfinal_2026-11-13_14-34-08"


class ActPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.skills = load_skills(SKILLS)
        self.cup = self.skills[Intent.CUP]
        self.config = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_cup_index_names_the_published_contract(self) -> None:
        self.assertTrue(self.cup.ready)
        self.assertEqual(self.cup.policy_path, POLICY)
        self.assertEqual(self.cup.revision, "3240600b11fa941067649a06e00d03d4d8402145")
        self.assertEqual(self.cup.dataset_repo_id, "axellin/cupfinal")
        self.assertEqual(self.cup.robot_type, "so_follower")
        self.assertEqual(self.cup.camera, "top")
        self.assertEqual(self.cup.task, "uo")
        self.assertEqual(self.cup.image_shape, (3, 480, 640))
        self.assertEqual(self.cup.action_names[0], "shoulder_pan.pos")
        self.assertEqual(self.cup.action_names[-1], "gripper.pos")
        self.assertFalse(self.skills[Intent.WATER].ready)
        self.assertFalse(self.skills[Intent.TISSUE].ready)

    def test_published_config_matches_and_a_different_camera_does_not(self) -> None:
        validate_policy_config(self.config, self.cup)
        changed = json.loads(json.dumps(self.config))
        changed["input_features"]["observation.images.front"] = changed["input_features"].pop("observation.images.top")
        with self.assertRaisesRegex(ValueError, "input_features"):
            validate_policy_config(changed, self.cup)

    def test_rollout_uses_the_top_camera_and_a_finite_duration(self) -> None:
        command = rollout_argv(self.cup, port="/dev/ttyACM0", camera_index="0", duration=60)
        self.assertEqual(command[0], "lerobot-rollout")
        self.assertIn("--strategy.type=base", command)
        self.assertIn("--robot.type=so_follower", command)
        self.assertIn("--robot.port=/dev/ttyACM0", command)
        self.assertIn(f"--policy.path={POLICY}", command)
        self.assertIn("--task=uo", command)
        self.assertIn("--duration=60", command)
        cameras = next(item for item in command if item.startswith("--robot.cameras="))
        self.assertIn("top:", cameras)
        self.assertIn("width: 640", cameras)
        self.assertIn("height: 480", cameras)
        self.assertIn("fps: 30", cameras)
        self.assertNotIn("front:", cameras)
        with self.assertRaises(ValueError):
            rollout_argv(self.cup, port="/dev/ttyACM0", camera_index="0", duration=0)

    def test_runner_completes_the_workflow_and_a_missing_runner_does_not(self) -> None:
        calls: list[list[str]] = []
        robot = ActRobot(self.skills, port="/dev/ttyACM0", camera_index="0", runner=calls.append)
        workflow = RetrievalWorkflow(robot)
        request = RetrievalRequest("cup-1", Intent.CUP, "wlasl:cup")
        workflow.submit(request)
        self.assertEqual(workflow.status, Status.WAITING_RESULT)
        self.assertEqual(calls[0][0], "lerobot-rollout")

        idle = ActRobot(self.skills, port="/dev/ttyACM0", camera_index="0")
        with self.assertRaisesRegex(RuntimeError, "runner is not configured"):
            idle.execute(Intent.CUP)
        with self.assertRaisesRegex(ValueError, "No retrieval skill"):
            idle.execute(Intent.WATER)

    def test_command_prints_the_argv_without_marking_it_executed(self) -> None:
        result = run(self._parse("robot", "command", "--port", "/dev/ttyACM0", "--camera-index", "1", "--device", "cpu"))
        self.assertFalse(result["hardware_connected"])
        self.assertFalse(result["executed"])
        self.assertIn("--device=cpu", result["argv"])
        self.assertIn("--robot.cameras={ top: {type: opencv, index_or_path: 1, width: 640, height: 480, fps: 30} }", result["argv"])

        shown = run(self._parse("robot", "show"))
        self.assertEqual(shown["skills"]["request_cup"]["revision"], self.cup.revision)
        self.assertFalse(shown["hardware_connected"])

        checked = run(self._parse("robot", "check", "--config", str(FIXTURE)))
        self.assertTrue(checked["ok"])
        self.assertEqual(checked["repo_id"], POLICY)

    def test_policy_path_flag_overrides_the_environment(self) -> None:
        with patch.dict(os.environ, {"CUP_POLICY_PATH": "outputs/from-env"}):
            selected = run(self._parse(
                "robot", "command", "--port", "/dev/ttyACM0", "--camera-index", "0",
                "--policy-path", "outputs/from-flag",
            ))
            inherited = run(self._parse("robot", "command", "--port", "/dev/ttyACM0", "--camera-index", "0"))
        self.assertIn("--policy.path=outputs/from-flag", selected["argv"])
        self.assertIn("--policy.path=outputs/from-env", inherited["argv"])

    def _parse(self, *argv: str) -> argparse.Namespace:
        parser = argparse.ArgumentParser()
        commands = parser.add_subparsers(dest="command", required=True)
        add_command(commands)
        args = parser.parse_args(argv)
        args.skills = SKILLS
        return args


if __name__ == "__main__":
    unittest.main()
