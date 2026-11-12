"""Check the local WLASL catalog reader and gloss-to-intent mapping."""

import json
from pathlib import Path
import tempfile
import unittest

from gesture_aid.contracts import Intent, Status
from gesture_aid.perception.wlasl import dataset_status, load_gloss_map, request_from_gloss
from gesture_aid.robot.mock import MockRobot
from gesture_aid.workflow.controller import RetrievalWorkflow

REPO_ROOT = Path(__file__).resolve().parents[1]
GLOSS_MAP = REPO_ROOT / "configs" / "wlasl_gloss_map.json"


def _instance(video_id: str, split: str) -> dict[str, object]:
    return {
        "bbox": [0, 0, 10, 10],
        "fps": 25,
        "frame_end": -1,
        "frame_start": 1,
        "instance_id": 0,
        "signer_id": 1,
        "source": "fixture",
        "split": split,
        "url": "https://example.invalid/video",
        "variation_id": 0,
        "video_id": video_id,
    }


class WLASLTests(unittest.TestCase):
    def test_project_gloss_map_covers_both_retrieval_intents(self) -> None:
        mappings = load_gloss_map(GLOSS_MAP)
        self.assertEqual(mappings["water"].intent, Intent.WATER)
        self.assertEqual(mappings["tissue"].intent, Intent.TISSUE)
        self.assertEqual(mappings["water"].sign_id, "wlasl_water")
        self.assertEqual(mappings["tissue"].sign_id, "wlasl_tissue")

    def test_known_gloss_can_confirm_a_retrieval(self) -> None:
        mappings = load_gloss_map(GLOSS_MAP)
        request = request_from_gloss("Water", mappings)
        robot = MockRobot()
        workflow = RetrievalWorkflow(robot)
        workflow.submit(request)
        workflow.confirm(request.request_id)
        self.assertEqual(request.recognized_sign_id, "wlasl_water")
        self.assertEqual(robot.executed_skills, ["pick_water"])
        self.assertEqual(workflow.status, Status.WAITING_RESULT)

    def test_unmapped_gloss_stays_unclear(self) -> None:
        request = request_from_gloss("book", load_gloss_map(GLOSS_MAP))
        self.assertEqual(request.intent, Intent.UNCLEAR)
        self.assertEqual(request.recognized_sign_id, "wlasl_unmapped:book")

    def test_status_counts_present_and_missing_videos(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            videos = root / "videos"
            videos.mkdir()
            (videos / "water-train.mp4").write_bytes(b"fixture")
            catalog = [
                {"gloss": "water", "instances": [_instance("water-train", "train"), _instance("water-test", "test")]},
                {"gloss": "tissue", "instances": [_instance("tissue-val", "val")]},
                {"gloss": "book", "instances": [_instance("book-train", "train")]},
            ]
            (root / "WLASL_v0.3.json").write_text(json.dumps(catalog), encoding="utf-8")
            status = dataset_status(root, load_gloss_map(GLOSS_MAP))

        self.assertTrue(status["catalog_found"])
        self.assertEqual(status["catalog_glosses"], 3)
        self.assertEqual(status["catalog_instances"], 4)
        self.assertEqual(status["unmapped_instances"], 1)
        mapped = {row["gloss"]: row for row in status["mapped"]}
        self.assertEqual(mapped["water"]["videos_present"], 1)
        self.assertEqual(mapped["water"]["videos_missing"], 1)
        self.assertEqual(mapped["water"]["splits"], {"train": 1, "val": 0, "test": 1})
        self.assertEqual(mapped["tissue"]["videos_present"], 0)
        self.assertEqual(mapped["tissue"]["videos_missing"], 1)

    def test_missing_catalog_is_reported_without_reading_videos(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            status = dataset_status(Path(directory), load_gloss_map(GLOSS_MAP))
        self.assertFalse(status["catalog_found"])
        self.assertTrue(str(status["expected_catalog"]).endswith("WLASL_v0.3.json"))

    def test_invalid_frame_span_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            instance = _instance("bad", "train")
            instance["frame_start"] = 8
            instance["frame_end"] = 3
            (root / "WLASL_v0.3.json").write_text(
                json.dumps([{"gloss": "water", "instances": [instance]}]),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "invalid frame span"):
                dataset_status(root, load_gloss_map(GLOSS_MAP))


if __name__ == "__main__":
    unittest.main()
