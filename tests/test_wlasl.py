"""Verify subset fidelity, missing-video reports, and recognition label mapping."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from gesture_aid.contracts import Intent
from gesture_aid.datasets.wlasl import WLASLDataset, prepare_workspace, write_json
from gesture_aid.perception.wlasl import request_from_gloss


def video(video_id: str, split: str, frame_end: int = -1) -> dict:
    return {"video_id": video_id, "split": split, "fps": 25, "frame_start": 3,
            "frame_end": frame_end, "signer_id": 1, "bbox": [1, 2, 3, 4],
            "url": "https://example.invalid/clip.mp4"}


class WLASLTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.metadata = self.root / "annotations.json"
        self.entries = [
            {"gloss": "water", "instances": [video("001", "train", 10), video("002", "test")]},
            {"gloss": "tissue", "instances": [video("003", "val")]},
        ]
        write_json(self.metadata, self.entries)
        self.dataset = WLASLDataset(self.metadata)

    def test_subset_preserves_source_fields_and_split(self) -> None:
        subset = self.dataset.select(["water", "water"], "test")
        self.assertEqual(len(subset), 1)
        self.assertEqual(subset[0]["instances"], [self.entries[0]["instances"][1]])
        self.assertEqual(self.dataset.stats()["sample_count"], 3)

    def test_unknown_gloss_is_an_explicit_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown WLASL glosses"):
            self.dataset.select(["not-a-word"])

    def test_manifest_detects_nonempty_files_and_preserves_original_frames(self) -> None:
        videos = self.root / "videos"
        videos.mkdir()
        (videos / "001.mp4").write_bytes(b"presence fixture")
        (videos / "002.mp4").touch()
        manifest = self.dataset.manifest(videos, ["water"])
        self.assertEqual(manifest["present_count"], 1)
        self.assertEqual(manifest["samples"][0]["frame_start"], 3)
        self.assertEqual(manifest["samples"][1]["frame_end"], -1)
        self.assertFalse(manifest["samples"][1]["video_present"])

    def test_filename_traversal_is_rejected(self) -> None:
        self.entries[0]["instances"][0]["video_id"] = "../outside"
        write_json(self.metadata, self.entries)
        with self.assertRaisesRegex(ValueError, "safe filename"):
            WLASLDataset(self.metadata)

    def test_duplicate_labels_are_rejected(self) -> None:
        write_json(self.metadata, [self.entries[0], self.entries[0]])
        with self.assertRaisesRegex(ValueError, "duplicate gloss"):
            WLASLDataset(self.metadata)

    def test_invalid_frame_interval_is_rejected(self) -> None:
        self.entries[0]["instances"][0]["frame_end"] = 1
        write_json(self.metadata, self.entries)
        with self.assertRaisesRegex(ValueError, "frame range"):
            WLASLDataset(self.metadata)

    def test_prepare_copies_scripts_and_filtered_metadata(self) -> None:
        upstream = self.root / "upstream"
        kit = upstream / "start_kit"
        (kit / "scripts").mkdir(parents=True)
        for name in ["video_downloader.py", "preprocess.py", "C-UDA-1.0.pdf"]:
            (kit / name).write_bytes(b"fixture")
        output = self.root / "workspace"
        report = prepare_workspace(self.dataset, ["tissue"], output, upstream)
        self.assertEqual(report["sample_count"], 1)
        self.assertEqual(WLASLDataset(output / "WLASL_v0.3.json").stats()["gloss_count"], 1)
        self.assertTrue((output / "C-UDA-1.0.pdf").exists())
        self.assertEqual(json.loads(self.metadata.read_text()), self.entries)

    def test_gloss_mapping_normalizes_supported_words(self) -> None:
        lexicon = self.root / "lexicon.json"
        write_json(lexicon, {"entries": [{"gloss": "water", "intent": "request_water"}]})
        self.assertEqual(request_from_gloss(" Water ", lexicon).intent, Intent.WATER)
        self.assertEqual(request_from_gloss("book", lexicon).intent, Intent.UNCLEAR)

    def test_cli_export_and_manifest(self) -> None:
        output = self.root / "subset.json"
        result = subprocess.run([
            sys.executable, "-m", "gesture_aid.cli", "wlasl", "--metadata", str(self.metadata),
            "export", "--gloss", "water", "--split", "train", "--output", str(output),
        ], capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout)["sample_count"], 1)
        self.assertEqual(WLASLDataset(output).select()[0]["instances"][0]["frame_end"], 10)
        result = subprocess.run([
            sys.executable, "-m", "gesture_aid.cli", "wlasl", "--metadata", str(self.metadata),
            "manifest", "--videos-dir", str(self.root / "absent"), "--output", str(self.root / "manifest.json"),
        ], capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout)["missing_count"], 3)

    def test_cli_export_refuses_source_overwrite(self) -> None:
        result = subprocess.run([
            sys.executable, "-m", "gesture_aid.cli", "wlasl", "--metadata", str(self.metadata),
            "export", "--gloss", "water", "--output", str(self.metadata),
        ], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(self.metadata.read_text()), self.entries)


if __name__ == "__main__":
    unittest.main()
