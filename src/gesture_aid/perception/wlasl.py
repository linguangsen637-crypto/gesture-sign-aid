"""Read a local WLASL v0.3 drop and map glosses onto retrieval intents.

Videos and the official catalog stay outside Git. This module only indexes
files the team places under datasets/wlasl/.
"""

from dataclasses import dataclass
import json
from pathlib import Path
from uuid import uuid4

from gesture_aid.contracts import Intent, RetrievalRequest

CATALOG_NAME = "WLASL_v0.3.json"
VIDEOS_DIRNAME = "videos"
SPLITS = ("train", "val", "test")


@dataclass(frozen=True)
class GlossMapping:
    gloss: str
    intent: Intent
    sign_id: str


@dataclass(frozen=True)
class WLASLInstance:
    gloss: str
    video_id: str
    split: str
    frame_start: int
    frame_end: int
    fps: int
    signer_id: int
    instance_id: int
    variation_id: int
    bbox: tuple[int, int, int, int]
    source: str

    def video_file(self, videos_dir: Path) -> Path:
        return videos_dir / f"{self.video_id}.mp4"


def load_gloss_map(path: Path) -> dict[str, GlossMapping]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("mappings")
    if not isinstance(rows, list) or not rows:
        raise ValueError("WLASL gloss map must contain a non-empty mappings list.")
    mappings: dict[str, GlossMapping] = {}
    for row in rows:
        gloss = _required_text(row, "gloss").casefold()
        sign_id = _required_text(row, "sign_id")
        intent_text = _required_text(row, "intent")
        try:
            intent = Intent(intent_text)
        except ValueError as error:
            raise ValueError(f"Unsupported intent for gloss {gloss}.") from error
        if intent == Intent.UNCLEAR:
            raise ValueError(f"Gloss {gloss} cannot map to unclear.")
        if gloss in mappings:
            raise ValueError(f"Duplicate WLASL gloss mapping: {gloss}.")
        mappings[gloss] = GlossMapping(gloss, intent, sign_id)
    return mappings


def load_catalog(path: Path) -> list[WLASLInstance]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("WLASL catalog must be a list of gloss entries.")
    instances: list[WLASLInstance] = []
    for entry in payload:
        if not isinstance(entry, dict):
            raise ValueError("Each WLASL gloss entry must be an object.")
        gloss = _required_text(entry, "gloss").casefold()
        raw_instances = entry.get("instances")
        if not isinstance(raw_instances, list):
            raise ValueError(f"Gloss {gloss} is missing its instance list.")
        for raw in raw_instances:
            if not isinstance(raw, dict):
                raise ValueError(f"Gloss {gloss} contains a non-object instance.")
            instances.append(_instance(gloss, raw))
    return instances


def request_from_gloss(gloss: str, gloss_map: dict[str, GlossMapping]) -> RetrievalRequest:
    normalized = gloss.strip().casefold()
    if not normalized:
        raise ValueError("A recognized gloss must be nonempty.")
    mapping = gloss_map.get(normalized)
    if mapping is None:
        return RetrievalRequest(str(uuid4()), Intent.UNCLEAR, f"wlasl_unmapped:{normalized}")
    return RetrievalRequest(str(uuid4()), mapping.intent, mapping.sign_id)


def dataset_status(root: Path, gloss_map: dict[str, GlossMapping]) -> dict[str, object]:
    catalog_path = root / CATALOG_NAME
    videos_dir = root / VIDEOS_DIRNAME
    if not catalog_path.is_file():
        return {
            "catalog_found": False,
            "expected_catalog": str(catalog_path),
            "expected_videos": str(videos_dir),
        }
    instances = load_catalog(catalog_path)
    mapped_rows = []
    unmapped_instances = 0
    for gloss, mapping in gloss_map.items():
        selected = [item for item in instances if item.gloss == gloss]
        split_counts = {split: 0 for split in SPLITS}
        present = 0
        missing = 0
        for item in selected:
            split_counts[item.split] += 1
            if item.video_file(videos_dir).is_file():
                present += 1
            else:
                missing += 1
        mapped_rows.append({
            "gloss": mapping.gloss,
            "intent": mapping.intent.value,
            "sign_id": mapping.sign_id,
            "instances": len(selected),
            "splits": split_counts,
            "videos_present": present,
            "videos_missing": missing,
        })
    mapped_glosses = set(gloss_map)
    for item in instances:
        if item.gloss not in mapped_glosses:
            unmapped_instances += 1
    return {
        "catalog_found": True,
        "catalog_path": str(catalog_path),
        "videos_dir": str(videos_dir),
        "catalog_glosses": len({item.gloss for item in instances}),
        "catalog_instances": len(instances),
        "unmapped_instances": unmapped_instances,
        "mapped": mapped_rows,
    }


def _instance(gloss: str, raw: dict[str, object]) -> WLASLInstance:
    split = _required_text(raw, "split")
    if split not in SPLITS:
        raise ValueError(f"Gloss {gloss} has an unsupported split.")
    frame_start = _required_int(raw, "frame_start")
    frame_end = _required_int(raw, "frame_end")
    if frame_start < 1 or (frame_end != -1 and frame_end < frame_start):
        raise ValueError(f"Gloss {gloss} has an invalid frame span.")
    fps = _required_int(raw, "fps")
    if fps < 1:
        raise ValueError(f"Gloss {gloss} has an invalid frame rate.")
    bbox = raw.get("bbox")
    if (
        not isinstance(bbox, list)
        or len(bbox) != 4
        or any(not isinstance(value, int) for value in bbox)
    ):
        raise ValueError(f"Gloss {gloss} has an invalid bounding box.")
    return WLASLInstance(
        gloss=gloss,
        video_id=_required_text(raw, "video_id"),
        split=split,
        frame_start=frame_start,
        frame_end=frame_end,
        fps=fps,
        signer_id=_required_int(raw, "signer_id"),
        instance_id=_required_int(raw, "instance_id"),
        variation_id=_required_int(raw, "variation_id"),
        bbox=(bbox[0], bbox[1], bbox[2], bbox[3]),
        source=_required_text(raw, "source"),
    )


def _required_text(raw: object, field: str) -> str:
    if not isinstance(raw, dict):
        raise ValueError(f"Expected an object with {field}.")
    value = raw.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Field {field} must be nonempty text.")
    return value.strip()


def _required_int(raw: dict[str, object], field: str) -> int:
    value = raw.get(field)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"Field {field} must be an integer.")
    return value
