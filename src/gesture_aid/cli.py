"""Command-line entry point for the simulated end-to-end workflow."""

import argparse
import json
from pathlib import Path

from gesture_aid.contracts import Intent, Status
from gesture_aid.datasets import cli as datasets_cli
from gesture_aid.perception.mock import simulate_recognition
from gesture_aid.perception.wlasl import request_from_gloss
from gesture_aid.perception import camera, template_cli
from gesture_aid.robot.lab import LabError, MakerModsRobot, load_profile
from gesture_aid.robot.mock import MockRobot
from gesture_aid.workflow.controller import RetrievalWorkflow


def main() -> None:
    parser = argparse.ArgumentParser(description="SignAid simulated retrieval workflow")
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo", help="Run simulated recognition and robot execution")
    selection = demo.add_mutually_exclusive_group()
    selection.add_argument("--intent", choices=[item.value for item in Intent])
    selection.add_argument("--gloss", help="Simulate a recognizer's WLASL word label")
    demo.add_argument("--lexicon", type=Path, default=Path("configs/sign_lexicon.json"))
    # Accept older scripts while automatic execution is the default.
    demo.add_argument("--confirm", action="store_true", help=argparse.SUPPRESS)
    demo.add_argument("--delivered", action="store_true", help="Simulate a positive delivery report")
    datasets_cli.add_commands(commands)
    camera.add_command(commands)
    template_cli.add_commands(commands)
    robot_command = commands.add_parser("robot", help="Check or run the physical SO-101")
    robot_action = robot_command.add_subparsers(dest="robot_command", required=True)
    robot_status = robot_action.add_parser("status", help="Read the arm without moving it")
    robot_run = robot_action.add_parser("run", help="Run one skill on the physical arm")
    robot_stop = robot_action.add_parser("stop", help="Stop the current arm session")
    for robot_parser in (robot_status, robot_run, robot_stop):
        robot_parser.add_argument("--config", type=Path, default=Path("configs/local.robot.json"))
    robot_run.add_argument("--intent", default=Intent.CUP.value, choices=[item.value for item in Intent if item != Intent.UNCLEAR])
    args = parser.parse_args()
    if args.command == "templates":
        try:
            result = template_cli.run(args)
        except (OSError, ValueError, ImportError, RuntimeError) as error:
            parser.exit(2, f"Template error: {error}\n")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if args.command == "camera":
        try:
            camera.run(args)
        except (OSError, ValueError, ImportError, RuntimeError) as error:
            parser.exit(2, f"Camera error: {error}\n")
        return
    if args.command == "robot":
        try:
            robot = MakerModsRobot(load_profile(args.config).pin_final_cup())
            if args.robot_command == "status":
                result = robot.status()
            elif args.robot_command == "stop":
                result = robot.stop()
            else:
                request = simulate_recognition(Intent(args.intent))
                workflow = RetrievalWorkflow(robot)
                workflow.submit(request)
                result = {
                    "mode": "hardware",
                    "request_id": request.request_id,
                    "intent": request.intent.value,
                    "status": workflow.status.value,
                    "executed_skills": robot.executed_skills,
                    "robot_status": robot.last_status,
                }
        except (LabError, OSError, ValueError, RuntimeError) as error:
            parser.exit(2, f"Robot error: {error}\n")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if args.command == "wlasl":
        try:
            result = datasets_cli.run(args)
        except (OSError, ValueError, KeyError) as error:
            parser.exit(2, f"WLASL error: {error}\n")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    try:
        if args.gloss is not None:
            request = request_from_gloss(args.gloss, args.lexicon)
        else:
            request = simulate_recognition(Intent(args.intent or Intent.CUP.value))
    except (OSError, ValueError, KeyError) as error:
        parser.exit(2, f"Configuration error: {error}\n")
    robot = MockRobot()
    workflow = RetrievalWorkflow(robot)
    workflow.submit(request)
    if args.delivered and workflow.status == Status.WAITING_RESULT:
        workflow.record_result(request.request_id, delivered=True)
    print(json.dumps({
        "mode": "simulation",
        "request_id": request.request_id,
        "intent": request.intent.value,
        "recognized_sign_id": request.recognized_sign_id,
        "status": workflow.status.value,
        "executed_skills": robot.executed_skills,
        "delivery_report": "simulated_positive" if args.delivered and workflow.status == Status.COMPLETED else None,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
