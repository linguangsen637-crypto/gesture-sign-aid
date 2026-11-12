"""Read WLASL annotations while retaining upstream labels and split metadata."""

from collections import Counter
import json
from pathlib import Path
import re
import shutil
import tempfile


DEFAULT_UPSTREAM = Path("third_party/WLASL")
DEFAULT_METADATA = DEFAULT_UPSTREAM / "start_kit/WLASL_v0.3.json"
UPSTREAM_COMMIT = "ac00e6be631c1a2a486621b65f202219f3964d6b"


def write_json(path: Path, content: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(json.dumps(content, ensure_ascii=False, indent=2) + "\n")
            stream.flush()
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


class WLASLDataset:
    def __init__(self, metadata: Path = DEFAULT_METADATA) -> None:
        self.metadata = Path(metadata)
        if not self.metadata.is_file():
            raise FileNotFoundError(
                f"WLASL metadata missing at {self.metadata}. "
                "Run git submodule update --init --recursive, or supply --metadata."
            )
        entries = json.loads(self.metadata.read_text(encoding="utf-8"))
        if not isinstance(entries, list):
            raise ValueError("WLASL metadata must be a list of gloss entries.")
        self.entries: dict[str, dict] = {}
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("gloss"), str):
                raise ValueError("Every WLASL entry must contain a string gloss.")
            gloss = entry["gloss"]
            if not gloss or gloss in self.entries or not isinstance(entry.get("instances"), list):
                raise ValueError(f"Invalid or duplicate gloss entry: {gloss!r}")
            for instance in entry["instances"]:
                self._validate_instance(instance)
            self.entries[gloss] = entry

    @staticmethod
    def _validate_instance(instance: object) -> None:
        if not isinstance(instance, dict):
            raise ValueError("Every video instance must be an object.")
        video_id = instance.get("video_id")
        if not isinstance(video_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", video_id):
            raise ValueError("Video identifiers must be safe filename components.")
        if instance.get("split") not in {"train", "val", "test"}:
            raise ValueError(f"Invalid split for video {video_id}.")
        fps = instance.get("fps")
        if not isinstance(fps, (int, float)) or isinstance(fps, bool) or fps <= 0:
            raise ValueError(f"Invalid fps for video {video_id}.")
        start, end = instance.get("frame_start"), instance.get("frame_end")
        if type(start) is not int or type(end) is not int or start < 1 or (end != -1 and end < start):
            raise ValueError(f"Invalid frame range for video {video_id}.")
        if not isinstance(instance.get("url"), str):
            raise ValueError(f"Missing source URL for video {video_id}.")

    def select(self, glosses: list[str] | None = None, split: str | None = None) -> list[dict]:
        selected = list(dict.fromkeys(glosses)) if glosses else list(self.entries)
        missing = sorted(set(selected) - self.entries.keys())
        if missing:
            raise ValueError("Unknown WLASL glosses: " + ", ".join(missing))
        if split is not None and split not in {"train", "val", "test"}:
            raise ValueError(f"Invalid split: {split}")
        return [
            {**self.entries[gloss], "instances": [
                instance for instance in self.entries[gloss]["instances"]
                if split is None or instance["split"] == split
            ]}
            for gloss in selected
        ]

    def stats(self, glosses: list[str] | None = None) -> dict:
        entries = self.select(glosses)
        return {
            "language": "ASL",
            "annotation_path": str(self.metadata),
            "gloss_count": len(entries),
            "sample_count": sum(len(entry["instances"]) for entry in entries),
            "glosses": [
                {"gloss": entry["gloss"], "samples": len(entry["instances"]),
                 "splits": dict(Counter(item["split"] for item in entry["instances"]))}
                for entry in entries
            ],
        }

    def manifest(self, videos_dir: Path, glosses: list[str] | None = None, split: str | None = None) -> dict:
        samples = []
        for entry in self.select(glosses, split):
            for instance in entry["instances"]:
                video = videos_dir / f"{instance['video_id']}.mp4"
                samples.append({
                    **instance,
                    "gloss": entry["gloss"],
                    "video_path": str(video.resolve()),
                    "video_present": video.is_file() and video.stat().st_size > 0,
                })
        return {
            "dataset": "WLASL", "language": "ASL", "annotation_path": str(self.metadata.resolve()),
            "video_layout": "preprocessed clips named <video_id>.mp4",
            "sample_count": len(samples),
            "present_count": sum(item["video_present"] for item in samples),
            "samples": samples,
        }


def prepare_workspace(dataset: WLASLDataset, glosses: list[str], output: Path, upstream: Path) -> dict:
    """Prepare upstream scripts and filtered metadata for an explicit download run."""
    entries = dataset.select(glosses)
    kit = upstream / "start_kit"
    required = [kit / name for name in ["video_downloader.py", "preprocess.py", "C-UDA-1.0.pdf", "scripts"]]
    for path in required:
        if not path.exists():
            raise FileNotFoundError(f"Upstream source missing: {path}")
    # Keep the source annotations intact if a caller selects a source directory.
    target_metadata = output / "WLASL_v0.3.json"
    if output.resolve() == kit.resolve() or target_metadata.resolve() == dataset.metadata.resolve():
        raise ValueError("Choose a workspace separate from the source metadata directory.")
    output.mkdir(parents=True, exist_ok=True)
    for path in required:
        destination = output / path.name
        if path.is_dir():
            shutil.copytree(path, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(path, destination)
    write_json(target_metadata, entries)
    provenance = {
        "source_repository": "https://github.com/dxli94/WLASL",
        "source_commit": UPSTREAM_COMMIT,
        "language": "ASL", "glosses": list(dict.fromkeys(glosses)),
        "sample_count": sum(len(entry["instances"]) for entry in entries),
    }
    write_json(output / "signaid-source.json", provenance)
    return {**provenance, "workspace": str(output.resolve())}
