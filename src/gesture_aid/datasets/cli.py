"""WLASL metadata and local video preparation commands."""

import argparse
from pathlib import Path

from gesture_aid.datasets.wlasl import DEFAULT_METADATA, DEFAULT_UPSTREAM, WLASLDataset, prepare_workspace, write_json


def add_commands(commands: argparse._SubParsersAction) -> None:
    parser = commands.add_parser("wlasl", help="Inspect WLASL and prepare selected videos")
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    actions = parser.add_subparsers(dest="dataset_command", required=True)
    stats = actions.add_parser("stats", help="Count samples by gloss and split")
    stats.add_argument("--gloss", nargs="+")
    search = actions.add_parser("search", help="Search available gloss names")
    search.add_argument("query")
    export = actions.add_parser("export", help="Write a filtered upstream-format annotation file")
    export.add_argument("--gloss", nargs="+", required=True)
    export.add_argument("--split", choices=["train", "val", "test"])
    export.add_argument("--output", type=Path, required=True)
    prepare = actions.add_parser("prepare", help="Prepare scripts and annotations for selected glosses")
    prepare.add_argument("--gloss", nargs="+", required=True)
    prepare.add_argument("--output", type=Path, default=Path("data/wlasl"))
    prepare.add_argument("--upstream", type=Path, default=DEFAULT_UPSTREAM)
    manifest = actions.add_parser("manifest", help="Index preprocessed local clips and report missing files")
    manifest.add_argument("--gloss", nargs="+")
    manifest.add_argument("--split", choices=["train", "val", "test"])
    manifest.add_argument("--videos-dir", type=Path, required=True)
    manifest.add_argument("--output", type=Path, required=True)


def run(args: argparse.Namespace) -> dict:
    dataset = WLASLDataset(args.metadata)
    if args.dataset_command == "stats":
        return dataset.stats(args.gloss)
    if args.dataset_command == "search":
        return {"glosses": [word for word in dataset.entries if args.query.casefold() in word.casefold()]}
    if args.dataset_command == "prepare":
        return prepare_workspace(dataset, args.gloss, args.output, args.upstream)
    if args.dataset_command == "export":
        if args.output.resolve() == args.metadata.resolve():
            raise ValueError("Export path must differ from source metadata.")
        entries = dataset.select(args.gloss, args.split)
        write_json(args.output, entries)
        return {"output": str(args.output), "gloss_count": len(entries),
                "sample_count": sum(len(entry["instances"]) for entry in entries)}
    manifest = dataset.manifest(args.videos_dir, args.gloss, args.split)
    write_json(args.output, manifest)
    return {"output": str(args.output), "sample_count": manifest["sample_count"],
            "present_count": manifest["present_count"],
            "missing_count": manifest["sample_count"] - manifest["present_count"]}
