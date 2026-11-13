"""Check the physical-arm adapter without opening a serial port."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from gesture_aid.contracts import Intent
from gesture_aid.robot.lab import LabError, MakerModsRobot, load_profile


class ScriptedClient:
    def __init__(self, gets):
        self.gets = {path: list(items) for path, items in gets.items()}
        self.posted = []

    def get(self, path, query=None):
        del query
        try:
            return self.gets[path].pop(0)
        except (KeyError, IndexError) as error:
            raise AssertionError(f"Unexpected GET {path}") from error

    def post(self, path, body=None):
        self.posted.append((path, body))
        return {"success": True, "message": "ok"}


def profile(root: Path, policy: Path | str | None = None):
    policy_path = policy or (root / "pretrained_model")
    config = {
        "base_url": "http://lab",
        "robot_name": "yoho",
        "follower_port": "/dev/follower",
        "follower_config": "yoho",
        "leader_port": "/dev/leader",
        "leader_config": "yoho",
        "camera_bindings": {"top": "top"},
        "camera_dims": {"top": {"width": 640, "height": 480}},
        "skills": {"request_cup": {"skill": "pick_cup", "policy_path": str(policy_path), "duration_s": 30}},
    }
    path = root / "robot.json"
    path.write_text(json.dumps(config))
    return load_profile(path)


class Clock:
    def __init__(self):
        self.now = 0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class LabRobotTests(unittest.TestCase):
    def test_status_reports_a_powered_calibrated_arm(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            loaded = profile(root)
            (root / "pretrained_model").mkdir()
            robot = MakerModsRobot(loaded, ScriptedClient({
                "/api/v1/health": [{"status": "ok"}],
                "/api/v1/robots/yoho": [{"robot": {"arm_type": "so101", "follower_ready": True, "leader_ready": True, "cameras": [{"name": "top"}]}}],
                "/api/v1/available-ports": [{"ports": ["/dev/follower", "/dev/leader"]}],
                "/api/v1/inference-status": [{"inference_active": False, "shutting_down": False, "phase": None}],
                "/api/v1/supply-voltage": [{"success": True, "voltage": 12.2}],
                "/api/v1/policy-config": [{"image_features": {"top": {"height": 480, "width": 640}}}],
            }))
            report = robot.status()
        self.assertTrue(report["robot_connected"])
        self.assertEqual(report["voltage"], 12.2)
        self.assertTrue(report["policy_ready"])

    def test_status_stays_disconnected_when_voltage_cannot_be_read(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pretrained_model").mkdir()
            robot = MakerModsRobot(profile(root), ScriptedClient({
                "/api/v1/health": [{"status": "ok"}],
                "/api/v1/robots/yoho": [{"robot": {"follower_ready": True, "leader_ready": True, "cameras": []}}],
                "/api/v1/available-ports": [{"ports": ["/dev/follower"]}],
                "/api/v1/inference-status": [{"inference_active": False, "shutting_down": True}],
                "/api/v1/supply-voltage": [{"success": False, "message": "port busy"}],
                "/api/v1/policy-config": [{"image_features": {"top": {}}}],
            }))
            report = robot.status()
        self.assertFalse(report["robot_connected"])
        self.assertEqual(report["voltage_error"], "port busy")
        self.assertTrue(report["shutting_down"])

    def test_execute_waits_for_the_rollout_and_records_the_skill(self) -> None:
        clock = Clock()
        with TemporaryDirectory() as directory:
            root = Path(directory)
            loaded = profile(root)
            policy = loaded.skill_for(Intent.CUP).policy_path
            (root / "pretrained_model").mkdir()
            client = ScriptedClient({
                "/api/v1/inference-status": [
                    {"inference_active": False, "shutting_down": False},
                    {"inference_active": True, "policy_ref": policy, "phase": "running"},
                    {"inference_active": False, "shutting_down": False, "policy_ref": policy, "exited": True, "outcome": "ok", "phase": "stopped"},
                ],
            })
            robot = MakerModsRobot(loaded, client, clock=clock, sleep=clock.sleep)
            robot.execute(Intent.CUP)
        self.assertEqual(robot.executed_skills, ["pick_cup"])
        self.assertEqual(client.posted[0][0], "/api/v1/start-inference")
        self.assertEqual(client.posted[0][1]["follower_port"], "/dev/follower")
        self.assertEqual(client.posted[0][1]["camera_bindings"], {"top": "top"})
        self.assertEqual(client.posted[0][1]["policy_ref"], policy)

    def test_execute_stops_the_arm_when_the_rollout_exceeds_its_limit(self) -> None:
        clock = Clock()
        with TemporaryDirectory() as directory:
            root = Path(directory)
            loaded = profile(root)
            policy = loaded.skill_for(Intent.CUP).policy_path
            (root / "pretrained_model").mkdir()
            client = ScriptedClient({
                "/api/v1/inference-status": [
                    {"inference_active": False, "shutting_down": False},
                    *[{"inference_active": True, "policy_ref": policy, "phase": "running"}] * 300,
                ],
            })
            robot = MakerModsRobot(loaded, client, clock=clock, sleep=clock.sleep, timeout_margin_s=1)
            with self.assertRaisesRegex(RuntimeError, "time limit"):
                robot.execute(Intent.CUP)
        self.assertEqual(client.posted[-1][0], "/api/v1/stop-inference")
        self.assertEqual(robot.executed_skills, [])

    def test_request_cup_matches_the_makermods_run_on_robot(self) -> None:
        with TemporaryDirectory() as directory:
            loaded = profile(Path(directory))
            pinned = loaded.pin_final_cup()
        skill = pinned.skill_for(Intent.CUP)
        self.assertEqual(skill.policy_path, "axellin/act_cupfinal_2026-11-13_14-34-08@checkpoints/009000")
        self.assertEqual(skill.duration_s, 60)
        self.assertEqual(skill.task, "")

    def test_execute_sends_the_cupfinal_hub_checkpoint(self) -> None:
        clock = Clock()
        ref = "axellin/act_cupfinal_2026-11-13_14-34-08@checkpoints/010000"
        with TemporaryDirectory() as directory:
            loaded = profile(Path(directory), ref)
            client = ScriptedClient({
                "/api/v1/inference-status": [
                    {"inference_active": False, "shutting_down": False},
                    {"inference_active": True, "policy_ref": ref, "phase": "running"},
                    {"inference_active": False, "shutting_down": False, "policy_ref": ref, "exited": True, "outcome": "ok", "phase": "stopped"},
                ],
            })
            robot = MakerModsRobot(loaded, client, clock=clock, sleep=clock.sleep)
            robot.execute(Intent.CUP)
        self.assertEqual(client.posted[0][1]["policy_ref"], ref)

    def test_execute_refuses_a_busy_arm_and_a_missing_checkpoint(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pretrained_model").mkdir()
            busy = MakerModsRobot(profile(root), ScriptedClient({
                "/api/v1/inference-status": [{"inference_active": False, "shutting_down": True}],
            }))
            with self.assertRaisesRegex(RuntimeError, "busy"):
                busy.execute(Intent.CUP)
            missing = MakerModsRobot(profile(root, root / "missing-policy"), ScriptedClient({
                "/api/v1/inference-status": [{"inference_active": False, "shutting_down": False}],
            }))
            with self.assertRaisesRegex(RuntimeError, "checkpoint"):
                missing.execute(Intent.CUP)

    def test_invalid_configuration_is_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "robot.json"
            path.write_text("{}")
            with self.assertRaises(LabError):
                load_profile(path)
