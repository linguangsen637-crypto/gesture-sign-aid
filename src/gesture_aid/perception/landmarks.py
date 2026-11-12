"""Shared MediaPipe extraction for webcam frames and reference video clips."""
from pathlib import Path
import cv2
import numpy as np


class LandmarkExtractor:
    def __init__(self, model_dir: Path):
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions, vision
        self.mp = mp
        # IMAGE mode prevents tracking state leaking across videos/browser sessions.
        self.hands = vision.HandLandmarker.create_from_options(vision.HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(model_dir / 'hand_landmarker.task'), delegate=BaseOptions.Delegate.CPU),
            running_mode=vision.RunningMode.IMAGE, num_hands=2))
        try:
            self.pose = vision.PoseLandmarker.create_from_options(vision.PoseLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=str(model_dir / 'pose_landmarker_lite.task'), delegate=BaseOptions.Delegate.CPU),
                running_mode=vision.RunningMode.IMAGE, num_poses=1))
        except Exception:
            self.hands.close()
            raise

    def close(self):
        self.hands.close()
        self.pose.close()

    def extract(self, bgr, timestamp):
        image = self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
        hands, pose = self.hands.detect(image), self.pose.detect(image)
        aspect = bgr.shape[1] / bgr.shape[0]
        feature = dict(t=float(timestamp), shape=np.zeros((2, 63)).tolist(), wrists=[[0., 0.], [0., 0.]], valid=[False, False], body=False)
        overlay = dict(hands=[], shoulders=[])
        center, scale = None, None
        if pose.pose_landmarks:
            points = pose.pose_landmarks[0]
            shoulders = [points[11], points[12]]
            if all(p.visibility >= .6 and p.presence >= .6 for p in shoulders):
                xy = np.array([[p.x * aspect, p.y] for p in shoulders])
                scale = np.linalg.norm(xy[0] - xy[1])
                if scale > .05:
                    center = xy.mean(axis=0)
                    feature['body'] = True
                    overlay['shoulders'] = [[p.x, p.y] for p in shoulders]
        # Keep raw model handedness consistently for unmirrored video and webcam.
        # Do not independently rotate/reflection-normalize hands: orientation is meaningful.
        chosen = {}
        for points, categories in zip(hands.hand_landmarks, hands.handedness):
            cat = categories[0]
            slot = 0 if cat.category_name == 'Left' else 1
            if cat.score < .6 or (slot in chosen and chosen[slot][0] >= cat.score):
                continue
            chosen[slot] = (cat.score, points, cat.category_name)
        for slot, (_, points, name) in chosen.items():
            xyz = np.array([[p.x * aspect, p.y, p.z * aspect] for p in points])
            palm = np.linalg.norm(xyz[9, :2] - xyz[0, :2])
            if palm < .008:
                continue
            local = (xyz - xyz[0]) / palm
            if not np.isfinite(local).all() or np.abs(local).max() > 20:
                continue
            feature['valid'][slot] = True
            feature['shape'][slot] = local.flatten().tolist()
            if feature['body']:
                feature['wrists'][slot] = ((xyz[0, :2] - center) / scale).tolist()
            overlay['hands'].append(dict(side=name, points=[[p.x, p.y] for p in points]))
        return feature, overlay
