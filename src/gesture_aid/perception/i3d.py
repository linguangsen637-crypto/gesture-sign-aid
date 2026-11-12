"""Local inference using the pinned WLASL I3D implementation."""

import importlib.util
from pathlib import Path

import cv2
import numpy as np
import torch


class I3DRecognizer:
    def __init__(self, project: Path, model_dir: Path) -> None:
        source = project / "third_party/WLASL/code/I3D/pytorch_i3d.py"
        spec = importlib.util.spec_from_file_location("wlasl_i3d", source)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Cannot load WLASL implementation: {source}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.labels = {}
        for line in (model_dir / "labels.txt").read_text().splitlines():
            index, label = line.split(maxsplit=1)
            self.labels[int(index)] = label.strip()
        if set(self.labels) != set(range(len(self.labels))):
            raise ValueError("Model labels must use contiguous zero-based indices.")
        state = torch.load(model_dir / "model.pt", map_location="cpu", weights_only=True)
        self.model = module.InceptionI3d(len(self.labels), in_channels=3)
        self.model.load_state_dict(state, strict=True)
        self.model.eval()
        torch.set_num_threads(min(4, torch.get_num_threads()))

    def predict(self, frames: list[np.ndarray]) -> list[dict]:
        if not 16 <= len(frames) <= 64:
            raise ValueError("Provide 16 to 64 frames in chronological order.")
        # Browser provides an undistorted square ROI. Keep the upstream video's
        # BGR channel order and [-1, 1] normalization, then center-crop to 224.
        images = [cv2.resize(frame, (256, 256))[16:240, 16:240] for frame in frames]
        array = np.stack(images).astype(np.float32) / 127.5 - 1
        inputs = torch.from_numpy(array.transpose(3, 0, 1, 2).copy()).unsqueeze(0)
        with torch.inference_mode():
            scores = self.model(inputs).mean(dim=2).softmax(dim=1)[0]
        values, indices = scores.topk(min(5, len(self.labels)))
        return [
            {"gloss": self.labels[index], "score": score}
            for score, index in zip(values.tolist(), indices.tolist())
        ]
