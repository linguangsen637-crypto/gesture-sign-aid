"""Command-line entry point for the simulated workflow and local WLASL index."""

import argparse
import json
from pathlib import Path

from gesture_aid.contracts import Intent, Status
from gesture_aid.perception.mock import simulate_recognition
from gesture_aid.perception.wlasl import dataset_status, load_gloss_map
from gesture_aid.robot.mock import MockRobot
from gesture_aid.workflow.controller import RetrievalWorkflow


def main() -> None:
    parser = argparse.ArgumentParser(description="SignAid simulated retrieval workflow")
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo", help="Run simulated recognition and robot execution")
    demo.add_argument("--intent", choices=[item.value for item in Intent], default=Intent.WATER.value)
    demo.add_argument("--confirm", action="store_true", help="Simulate user confirmation")
    demo.add_argument("--delivered", action="store_true", help="Simulate a positive delivery report")
    wlasl = commands.add_parser("wlasl-status", help="Index a local WLASL v0.3 directory")
    wlasl.add_argument("--root", type=Path, default=Path("datasets/wlasl"))
    wlasl.add_argument("--map", type=Path, default=Path("configs/wlasl_gloss_map.json"))
    args = parser.parse_args()
    if args.command == "wlasl-status":
        report_wlasl(args.root, args.map)
        return
    if args.delivered and not args.confirm:
        parser.error("--delivered requires --confirm")

    request = simulate_recognition(Intent(args.intent))
    robot = MockRobot()
    workflow = RetrievalWorkflow(robot)
    workflow.submit(request)
    if args.confirm and workflow.status == Status.WAITING_CONFIRMATION:
        workflow.confirm(request.request_id)
    if args.delivered and workflow.status == Status.WAITING_RESULT:
        workflow.record_result(request.request_id, delivered=True)
    print(json.dumps({
        "mode": "simulation",
        "request_id": request.request_id,
        "intent": request.intent.value,
        "status": workflow.status.value,
        "executed_skills": robot.executed_skills,
        "delivery_report": "simulated_positive" if args.delivered and workflow.status == Status.COMPLETED else None,
    }, ensure_ascii=False, indent=2))


def report_wlasl(root: Path, gloss_map_path: Path) -> None:
    report = dataset_status(root, load_gloss_map(gloss_map_path))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["catalog_found"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
