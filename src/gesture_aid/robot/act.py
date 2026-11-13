"""Validate the indexed ACT policy and prepare a LeRobot rollout command.

Preparing the command does not open a serial port or send motor targets.
"""

import json
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from gesture_aid.contracts import Intent
from gesture_aid.robot.skills import Skill, describe

Runner = Callable[[list[str]], None]
MAX_DURATION_S = 600


def validate_policy_config(config: dict, skill: Skill) -> None:
    """Raise unless this config is the indexed ACT contract for the skill."""
    if not skill.ready:
        raise ValueError(f"{skill.name} has no published policy to check.")
    if not isinstance(config, dict):
        raise ValueError("Policy config must be a JSON object.")
    mismatches: list[str] = []
    if config.get("type") != "act":
        mismatches.append("type")
    if config.get("repo_id") != skill.repo_id:
        mismatches.append("repo_id")
    if config.get("chunk_size") != skill.chunk_size:
        mismatches.append("chunk_size")
    if config.get("n_action_steps") != skill.n_action_steps:
        mismatches.append("n_action_steps")
    if config.get("n_obs_steps") != skill.n_obs_steps:
        mismatches.append("n_obs_steps")
    inputs = config.get("input_features")
    outputs = config.get("output_features")
    if not isinstance(inputs, dict) or set(inputs) != {"observation.state", "observation.images.top"}:
        mismatches.append("input_features")
    else:
        _expect_feature(inputs, "observation.state", "STATE", skill.state_shape, mismatches)
        _expect_feature(inputs, "observation.images.top", "VISUAL", skill.image_shape, mismatches)
    if not isinstance(outputs, dict) or set(outputs) != {"action"}:
        mismatches.append("output_features")
    else:
        _expect_feature(outputs, "action", "ACTION", skill.action_shape, mismatches)
    if mismatches:
        raise ValueError("Policy config does not match the indexed skill: " + ", ".join(mismatches))


def rollout_argv(
    skill: Skill,
    *,
    port: str,
    camera_index: str,
    duration: float = 60,
    device: str | None = None,
    policy_path: str | None = None,
) -> list[str]:
    """Build one finite lerobot-rollout command for the verified robot environment."""
    if not skill.ready or skill.camera is None or skill.fps is None or skill.image_shape is None or skill.task is None:
        raise ValueError(f"{skill.name} has no published policy.")
    selected = skill if policy_path is None else replace(skill, policy_path=_command_token(policy_path, "policy path"))
    _command_token(selected.policy_path, "policy path")
    _command_token(port, "robot port")
    _command_token(camera_index, "camera index")
    seconds = _duration(duration)
    height = selected.image_shape[1]
    width = selected.image_shape[2]
    cameras = (
        f"{{ {selected.camera}: {{type: opencv, index_or_path: {camera_index}, "
        f"width: {width}, height: {height}, fps: {selected.fps}}} }}"
    )
    command = [
        "lerobot-rollout",
        "--strategy.type=base",
        f"--robot.type={selected.robot_type}",
        f"--robot.port={port}",
        f"--robot.cameras={cameras}",
        f"--policy.path={selected.policy_path}",
        f"--task={selected.task}",
        f"--duration={seconds}",
    ]
    if device is not None:
        if device not in {"cpu", "cuda", "mps"}:
            raise ValueError("Device must be cpu, cuda, or mps.")
        command.append(f"--device={device}")
    return command


class ActRobot:
    """Workflow adapter for a published ACT skill.

    ``execute`` returns after the injected runner finishes. Without a runner the
    prepared command is rejected and no motor target is produced.
    """

    def __init__(
        self,
        skills: dict[Intent, Skill],
        *,
        port: str | None = None,
        camera_index: str | None = None,
        duration: float = 60,
        device: str | None = None,
        policy_path: str | None = None,
        runner: Runner | None = None,
    ) -> None:
        self.skills = skills
        self.port = port
        self.camera_index = camera_index
        self.duration = duration
        self.device = device
        self.policy_path = policy_path
        self.runner = runner

    def execute(self, intent: Intent) -> None:
        skill = self.skills.get(intent)
        if skill is None or not skill.ready:
            raise ValueError("No retrieval skill for this intent.")
        if not self.port or self.camera_index is None:
            raise RuntimeError("SO-101 port and top camera index are required before the arm can move.")
        command = rollout_argv(
            skill,
            port=self.port,
            camera_index=self.camera_index,
            duration=self.duration,
            device=self.device,
            policy_path=self.policy_path,
        )
        if self.runner is None:
            raise RuntimeError("LeRobot runner is not configured. Prepared command: " + " ".join(command))
        self.runner(command)


def load_policy_config(path: Path) -> dict:
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("Policy config must be a JSON object.")
    return config


def describe_skills(skills: dict[Intent, Skill]) -> dict:
    return {
        "hardware_connected": False,
        "skills": {intent.value: describe(skill) for intent, skill in skills.items()},
    }


def _expect_feature(features: dict, key: str, feature_type: str, shape: tuple[int, ...] | None, mismatches: list[str]) -> None:
    feature = features.get(key)
    if not isinstance(feature, dict) or feature.get("type") != feature_type or feature.get("shape") != list(shape or ()):
        mismatches.append(key)


def _command_token(value: str, label: str) -> str:
    if not isinstance(value, str) or not value or value[:1] == "-" or any(char.isspace() or char in "={}#\"'" for char in value):
        raise ValueError(f"{label} contains characters that would change the rollout command.")
    return value


def _duration(value: float) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Duration must be a positive number of seconds.")
    if value <= 0 or value > MAX_DURATION_S:
        raise ValueError(f"Duration must be greater than 0 and at most {MAX_DURATION_S} seconds.")
    return format(float(value), "f").rstrip("0").rstrip(".")
