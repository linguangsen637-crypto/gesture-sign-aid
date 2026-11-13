"""Inspect the indexed ACT policy and print a rollout command."""

import argparse
import os
from pathlib import Path

from gesture_aid.contracts import Intent
from gesture_aid.robot.act import describe_skills, load_policy_config, rollout_argv, validate_policy_config
from gesture_aid.robot.skills import load_skills

DEFAULT_SKILLS = Path("configs/skills.example.json")


def add_command(commands: argparse._SubParsersAction) -> None:
    parser = commands.add_parser("robot", help="Inspect the indexed ACT policy without moving the arm")
    parser.add_argument("--skills", type=Path, default=DEFAULT_SKILLS)
    actions = parser.add_subparsers(dest="robot_command", required=True)
    actions.add_parser("show", help="Print the skill index")
    check = actions.add_parser("check", help="Compare a local policy config.json with the index")
    check.add_argument("--config", type=Path, required=True)
    command = actions.add_parser("command", help="Print one finite lerobot-rollout command")
    command.add_argument("--port", required=True)
    command.add_argument("--camera-index", required=True)
    command.add_argument("--duration", type=float, default=60)
    command.add_argument("--device", choices=["cpu", "cuda", "mps"])
    command.add_argument("--policy-path", help="Local directory or Hub id to pass as --policy.path")


def run(args: argparse.Namespace) -> dict:
    skills = load_skills(args.skills)
    if args.robot_command == "show":
        described = describe_skills(skills)
        described["skills_path"] = str(args.skills)
        return described
    if args.robot_command == "check":
        skill = skills[Intent.CUP]
        validate_policy_config(load_policy_config(args.config), skill)
        return {
            "ok": True,
            "hardware_connected": False,
            "skill": skill.name,
            "repo_id": skill.repo_id,
            "revision": skill.revision,
            "config": str(args.config),
        }
    skill = skills[Intent.CUP]
    policy_path = args.policy_path or os.environ.get("CUP_POLICY_PATH", "").strip() or None
    argv = rollout_argv(
        skill,
        port=args.port,
        camera_index=args.camera_index,
        duration=args.duration,
        device=args.device,
        policy_path=policy_path,
    )
    return {
        "hardware_connected": False,
        "executed": False,
        "skill": skill.name,
        "revision": skill.revision,
        "argv": argv,
        "note": "Start this command in the verified LeRobot environment after the hardware check.",
    }
