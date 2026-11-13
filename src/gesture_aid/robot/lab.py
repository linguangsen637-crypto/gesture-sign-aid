"""SO-101 execution through a local MakerMods Lab session.

The adapter owns starting and stopping one ACT rollout. It does not decide
whether the item reached the tray.
"""

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, replace
from pathlib import Path

from gesture_aid.contracts import Intent


class LabError(RuntimeError):
    """MakerMods Lab could not be reached or rejected the request."""


_HUB_POLICY_REF = re.compile(r"^[^@]+@(?:checkpoints/\d+|root)$")
# Same launch as MakerMods Policy studio → cupfinal → step 10000 → Run on robot.
FINAL_CUP_POLICY = "axellin/act_cupfinal_2026-11-13_14-34-08@checkpoints/010000"
FINAL_CUP_DURATION_S = 60


def _policy_available(policy_path: str) -> bool:
    return bool(_HUB_POLICY_REF.match(policy_path)) or Path(policy_path).is_dir()


@dataclass(frozen=True)
class SkillSpec:
    intent: Intent
    name: str
    policy_path: str
    task: str
    duration_s: int


@dataclass(frozen=True)
class RobotProfile:
    base_url: str
    robot_name: str
    arm_type: str
    mode: str
    follower_port: str
    follower_config: str
    leader_port: str
    leader_config: str
    camera_bindings: dict[str, str]
    camera_dims: dict[str, dict[str, int]]
    checkpoint_state_dim: int
    skills: dict[Intent, SkillSpec]

    def pin_final_cup(self) -> "RobotProfile":
        skill = self.skills.get(Intent.CUP)
        if skill is None:
            return self
        skills = dict(self.skills)
        skills[Intent.CUP] = SkillSpec(
            intent=skill.intent,
            name=skill.name,
            policy_path=FINAL_CUP_POLICY,
            task="",
            duration_s=FINAL_CUP_DURATION_S,
        )
        return replace(self, skills=skills)

    def skill_for(self, intent: Intent) -> SkillSpec:
        try:
            return self.skills[intent]
        except KeyError as error:
            raise ValueError("No retrieval skill for this intent.") from error

    def inference_body(self, skill: SkillSpec) -> dict:
        return {
            "follower_port": self.follower_port,
            "follower_config": self.follower_config,
            "policy_ref": skill.policy_path,
            "task": skill.task,
            "camera_bindings": self.camera_bindings,
            "camera_dims": self.camera_dims,
            "duration_s": skill.duration_s,
            "mode": self.mode,
            "robot_name": self.robot_name,
            "arm_type": self.arm_type,
            "checkpoint_state_dim": self.checkpoint_state_dim,
        }


class LabClient:
    def __init__(self, base_url: str, timeout: float = 30) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def get(self, path: str, query: dict | None = None) -> dict:
        return self._request("GET", path, query=query)

    def post(self, path: str, body: dict | None = None) -> dict:
        return self._request("POST", path, body=body or {})

    def _request(self, method: str, path: str, query: dict | None = None, body: dict | None = None) -> dict:
        url = self.base_url + path
        if query:
            url += "?" + urllib.parse.urlencode(query)
        data = None
        headers = {}
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = response.read()
        except urllib.error.HTTPError as error:
            raise LabError(_error_message(error)) from error
        except urllib.error.URLError as error:
            raise LabError(f"MakerMods Lab is not reachable at {self.base_url}: {error.reason}") from error
        if not payload:
            return {}
        parsed = json.loads(payload)
        if not isinstance(parsed, dict):
            raise LabError("MakerMods Lab returned an unexpected response.")
        return parsed


class MakerModsRobot:
    def __init__(self, profile: RobotProfile, client: LabClient | None = None, clock=time.monotonic, sleep=time.sleep, timeout_margin_s: float = 90) -> None:
        self.profile = profile
        self.client = client or LabClient(profile.base_url)
        self.clock = clock
        self.sleep = sleep
        self.timeout_margin_s = timeout_margin_s
        self.executed_skills: list[str] = []
        self.last_status: dict | None = None

    def status(self) -> dict:
        health = self.client.get("/api/v1/health")
        robot_payload = self.client.get(f"/api/v1/robots/{urllib.parse.quote(self.profile.robot_name)}")
        ports = self.client.get("/api/v1/available-ports").get("ports", [])
        inference = self.client.get("/api/v1/inference-status")
        record = robot_payload.get("robot", {})
        voltage = self.client.get("/api/v1/supply-voltage", {"port": self.profile.follower_port})
        skill = self.profile.skill_for(Intent.CUP) if Intent.CUP in self.profile.skills else None
        policy = _policy_status(self.client, skill, self.profile.camera_bindings)
        follower_present = self.profile.follower_port in ports
        connected = bool(voltage.get("success") and follower_present and record.get("follower_ready"))
        return {
            "mode": "hardware",
            "lab": health.get("status"),
            "robot_name": self.profile.robot_name,
            "robot_connected": connected,
            "arm_type": record.get("arm_type", self.profile.arm_type),
            "follower_port": self.profile.follower_port,
            "follower_present": follower_present,
            "follower_ready": bool(record.get("follower_ready")),
            "leader_port": self.profile.leader_port,
            "leader_present": self.profile.leader_port in ports if self.profile.leader_port else False,
            "leader_ready": bool(record.get("leader_ready")),
            "voltage": voltage.get("voltage"),
            "voltage_error": None if voltage.get("success") else voltage.get("message"),
            "cameras": [item.get("name") for item in record.get("cameras", [])],
            "policy_path": None if skill is None else skill.policy_path,
            "policy_ready": policy["ready"],
            "policy_error": policy["error"],
            "inference_active": bool(inference.get("inference_active")),
            "shutting_down": bool(inference.get("shutting_down")),
            "phase": inference.get("phase"),
        }

    def execute(self, intent: Intent) -> None:
        skill = self.profile.skill_for(intent)
        if not _policy_available(skill.policy_path):
            raise RuntimeError(f"ACT checkpoint is not available: {skill.policy_path}")
        current = self.client.get("/api/v1/inference-status")
        if current.get("inference_active") or current.get("shutting_down"):
            raise RuntimeError("The arm is busy. Wait until the current session has released the motors.")
        started = self.client.post("/api/v1/start-inference", self.profile.inference_body(skill))
        if started.get("success") is False:
            raise RuntimeError(started.get("message") or "Failed to start the arm.")
        self.last_status = self._wait(skill)
        outcome = self.last_status.get("outcome")
        if outcome not in {"ok", "ran_with_warning"}:
            message = self.last_status.get("error") or self.last_status.get("hint") or "The arm did not finish the skill."
            raise RuntimeError(str(message))
        self.executed_skills.append(skill.name)

    def stop(self) -> dict:
        result = self.client.post("/api/v1/stop-inference")
        self.last_status = result
        return result

    def _wait(self, skill: SkillSpec) -> dict:
        deadline = self.clock() + skill.duration_s + self.timeout_margin_s
        seen_active = False
        while self.clock() < deadline:
            status = self.client.get("/api/v1/inference-status")
            self.last_status = status
            if status.get("inference_active") and status.get("policy_ref") == skill.policy_path:
                seen_active = True
            elif _rollout_finished(status, skill.policy_path, seen_active):
                return status
            self.sleep(0.5)
        self.stop()
        raise RuntimeError("The arm did not finish before the time limit.")


def load_profile(path: Path) -> RobotProfile:
    try:
        raw = json.loads(path.read_text())
    except OSError as error:
        raise LabError(f"Robot configuration is not available: {path}") from error
    except json.JSONDecodeError as error:
        raise LabError(f"Robot configuration is not valid JSON: {path}") from error
    if not isinstance(raw, dict):
        raise LabError("Robot configuration must be an object.")
    skills = {}
    for intent_value, item in (raw.get("skills") or {}).items():
        intent = Intent(intent_value)
        if not isinstance(item, dict) or not str(item.get("policy_path", "")).strip():
            raise LabError(f"Skill {intent_value} needs a policy_path.")
        skills[intent] = SkillSpec(
            intent=intent,
            name=str(item.get("skill") or intent_value),
            policy_path=str(item["policy_path"]),
            task=str(item.get("task") or ""),
            duration_s=int(item.get("duration_s") or 30),
        )
    required = ("base_url", "robot_name", "follower_port", "follower_config")
    missing = [key for key in required if not str(raw.get(key, "")).strip()]
    if missing or not skills:
        raise LabError("Robot configuration needs the arm address and at least one skill.")
    return RobotProfile(
        base_url=str(raw["base_url"]),
        robot_name=str(raw["robot_name"]),
        arm_type=str(raw.get("arm_type") or "so101"),
        mode=str(raw.get("mode") or "single"),
        follower_port=str(raw["follower_port"]),
        follower_config=str(raw["follower_config"]),
        leader_port=str(raw.get("leader_port") or ""),
        leader_config=str(raw.get("leader_config") or ""),
        camera_bindings=dict(raw.get("camera_bindings") or {}),
        camera_dims=dict(raw.get("camera_dims") or {}),
        checkpoint_state_dim=int(raw.get("checkpoint_state_dim") or 6),
        skills=skills,
    )


def _policy_status(client: LabClient, skill: SkillSpec | None, bindings: dict[str, str]) -> dict:
    if skill is None or not _policy_available(skill.policy_path):
        return {"ready": False, "error": "ACT checkpoint is not available."}
    try:
        summary = client.get("/api/v1/policy-config", {"policy_ref": skill.policy_path})
    except LabError as error:
        return {"ready": False, "error": str(error)}
    expected = set((summary.get("image_features") or {}))
    if expected != set(bindings):
        return {"ready": False, "error": "Camera bindings do not match the checkpoint."}
    return {"ready": True, "error": None}


def _rollout_finished(status: dict, policy_path: str, seen_active: bool) -> bool:
    if status.get("inference_active") or status.get("shutting_down"):
        return False
    if status.get("policy_ref") != policy_path:
        return False
    return bool(status.get("exited") or status.get("phase") in {"stopped", "error", "aborted"} or seen_active)


def _error_message(error: urllib.error.HTTPError) -> str:
    raw = error.read().decode(errors="replace")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return raw or str(error.reason)
    if isinstance(parsed, dict):
        detail = parsed.get("detail") or parsed.get("message")
        if detail:
            return str(detail)
    return raw or str(error.reason)
