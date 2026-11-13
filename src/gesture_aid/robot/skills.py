"""Load retrieval-skill records. Weights stay outside this repository."""

import json
from dataclasses import dataclass
from pathlib import Path

from gesture_aid.contracts import Intent

PLACEHOLDER_PREFIX = "SET_"
REQUIRED_INTENTS = (Intent.CUP, Intent.WATER, Intent.TISSUE)
READY_FIELDS = (
    "repo_id",
    "revision",
    "dataset_repo_id",
    "dataset_revision",
    "task",
    "camera",
    "fps",
    "image_shape",
    "state_shape",
    "action_shape",
    "action_names",
    "chunk_size",
    "n_action_steps",
    "n_obs_steps",
    "lerobot_version",
    "checkpoint_device",
)


@dataclass(frozen=True)
class Skill:
    intent: Intent
    name: str
    policy_path: str
    robot_type: str
    repo_id: str | None = None
    revision: str | None = None
    dataset_repo_id: str | None = None
    dataset_revision: str | None = None
    task: str | None = None
    camera: str | None = None
    fps: int | None = None
    image_shape: tuple[int, ...] | None = None
    state_shape: tuple[int, ...] | None = None
    action_shape: tuple[int, ...] | None = None
    action_names: tuple[str, ...] = ()
    chunk_size: int | None = None
    n_action_steps: int | None = None
    n_obs_steps: int | None = None
    lerobot_version: str | None = None
    checkpoint_device: str | None = None

    @property
    def ready(self) -> bool:
        return bool(self.policy_path) and not self.policy_path.startswith(PLACEHOLDER_PREFIX)


def load_skills(path: Path) -> dict[Intent, Skill]:
    """Read the skill index. A ready policy must name its Hub revision and contract."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Skills file must be an object keyed by intent.")
    skills: dict[Intent, Skill] = {}
    for key, value in raw.items():
        try:
            intent = Intent(key)
        except ValueError as error:
            raise ValueError(f"Unknown skill intent: {key}") from error
        if intent in skills:
            raise ValueError(f"Duplicate skill intent: {intent.value}")
        if not isinstance(value, dict):
            raise ValueError(f"{intent.value} must be an object.")
        skills[intent] = _skill(intent, value)
    missing = [intent.value for intent in REQUIRED_INTENTS if intent not in skills]
    if missing:
        raise ValueError("Skills file is missing: " + ", ".join(missing))
    return skills


def describe(skill: Skill) -> dict:
    return {
        "skill": skill.name,
        "ready": skill.ready,
        "policy_path": skill.policy_path,
        "repo_id": skill.repo_id,
        "revision": skill.revision,
        "dataset_repo_id": skill.dataset_repo_id,
        "dataset_revision": skill.dataset_revision,
        "robot_type": skill.robot_type,
        "task": skill.task,
        "camera": skill.camera,
        "fps": skill.fps,
        "image_shape": list(skill.image_shape) if skill.image_shape else None,
        "state_shape": list(skill.state_shape) if skill.state_shape else None,
        "action_shape": list(skill.action_shape) if skill.action_shape else None,
        "action_names": list(skill.action_names),
        "chunk_size": skill.chunk_size,
        "n_action_steps": skill.n_action_steps,
        "n_obs_steps": skill.n_obs_steps,
        "lerobot_version": skill.lerobot_version,
        "checkpoint_device": skill.checkpoint_device,
    }


def _skill(intent: Intent, value: dict) -> Skill:
    name = _token(value.get("skill"), f"{intent.value} skill")
    policy_path = _text(value.get("policy_path"), f"{intent.value} policy_path")
    robot_type = _token(value.get("robot_type"), f"{intent.value} robot_type")
    ready = bool(policy_path) and not policy_path.startswith(PLACEHOLDER_PREFIX)
    if ready:
        missing = [field for field in READY_FIELDS if field not in value]
        if missing:
            raise ValueError(f"{intent.value} is missing: " + ", ".join(missing))
        _flag_value(policy_path, f"{intent.value} policy_path")
        image_shape = _shape(value.get("image_shape"), f"{intent.value} image_shape", 3)
        if image_shape[0] != 3:
            raise ValueError(f"{intent.value} image_shape must be channels-first RGB.")
        action_shape = _shape(value.get("action_shape"), f"{intent.value} action_shape", 1)
        action_names = _names(value.get("action_names"), action_shape[0], intent)
        return Skill(
            intent=intent,
            name=name,
            policy_path=policy_path,
            robot_type=robot_type,
            repo_id=_hub_id(value.get("repo_id"), f"{intent.value} repo_id"),
            revision=_sha(value.get("revision"), f"{intent.value} revision"),
            dataset_repo_id=_hub_id(value.get("dataset_repo_id"), f"{intent.value} dataset_repo_id"),
            dataset_revision=_sha(value.get("dataset_revision"), f"{intent.value} dataset_revision"),
            task=_task(value.get("task"), intent),
            camera=_token(value.get("camera"), f"{intent.value} camera"),
            fps=_positive_int(value.get("fps"), f"{intent.value} fps"),
            image_shape=image_shape,
            state_shape=_shape(value.get("state_shape"), f"{intent.value} state_shape", 1),
            action_shape=action_shape,
            action_names=action_names,
            chunk_size=_positive_int(value.get("chunk_size"), f"{intent.value} chunk_size"),
            n_action_steps=_positive_int(value.get("n_action_steps"), f"{intent.value} n_action_steps"),
            n_obs_steps=_positive_int(value.get("n_obs_steps"), f"{intent.value} n_obs_steps"),
            lerobot_version=_text(value.get("lerobot_version"), f"{intent.value} lerobot_version"),
            checkpoint_device=_token(value.get("checkpoint_device"), f"{intent.value} checkpoint_device"),
        )
    return Skill(intent=intent, name=name, policy_path=policy_path, robot_type=robot_type)


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string.")
    return value


def _token(value: object, label: str) -> str:
    text = _text(value, label)
    if not text.isidentifier():
        raise ValueError(f"{label} must be an identifier.")
    return text


def _hub_id(value: object, label: str) -> str:
    text = _text(value, label)
    owner, separator, name = text.partition("/")
    if not separator or not owner or not name or "/" in name or any(char.isspace() for char in text):
        raise ValueError(f"{label} must be a Hugging Face repo id.")
    return text


def _sha(value: object, label: str) -> str:
    text = _text(value, label)
    if len(text) != 40 or any(char not in "0123456789abcdef" for char in text):
        raise ValueError(f"{label} must be a 40-character commit SHA.")
    return text


def _task(value: object, intent: Intent) -> str:
    text = _text(value, f"{intent.value} task")
    if any(char.isspace() or char in "=\n\r#" for char in text):
        raise ValueError(f"{intent.value} task must be a single command token.")
    return text


def _positive_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive integer.")
    return value


def _shape(value: object, label: str, length: int) -> tuple[int, ...]:
    if not isinstance(value, list) or len(value) != length:
        raise ValueError(f"{label} must contain {length} positive integers.")
    return tuple(_positive_int(item, label) for item in value)


def _names(value: object, expected: int, intent: Intent) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) != expected:
        raise ValueError(f"{intent.value} action_names must match the action dimension.")
    names = tuple(_dotted_name(item, f"{intent.value} action name") for item in value)
    if len(set(names)) != len(names):
        raise ValueError(f"{intent.value} action_names must be unique.")
    return names


def _dotted_name(value: object, label: str) -> str:
    text = _text(value, label)
    parts = text.split(".")
    if not parts or any(not part.isidentifier() for part in parts):
        raise ValueError(f"{label} must be an identifier, optionally dotted.")
    return text


def _flag_value(value: str, label: str) -> str:
    if value[:1] == "-" or any(char.isspace() or char in "={}#\"'" for char in value):
        raise ValueError(f"{label} contains characters that would change the rollout command.")
    return value
