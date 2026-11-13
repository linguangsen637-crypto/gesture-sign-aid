"""Versioned landmark features, DTW templates and single-action event gating."""
from pathlib import Path
from uuid import uuid4
import json
import math
import numpy as np

VERSION = 1


def validate_frames(frames, minimum=8):
    if not isinstance(frames, list) or not minimum <= len(frames) <= 96:
        raise ValueError(f"Record {minimum}–96 landmark frames of one complete gesture.")
    last = -math.inf
    for f in frames:
        if not isinstance(f, dict):
            raise ValueError("Invalid feature frame")
        for key, shape in (("shape", (2, 63)), ("wrists", (2, 2)), ("valid", (2,))):
            a = np.asarray(f.get(key), dtype=float)
            if a.shape != shape or not np.isfinite(a).all() or np.abs(a).max() > 100:
                raise ValueError(f"Invalid {key} features")
        if any(type(v) is not bool for v in f['valid']) or type(f.get('body')) is not bool:
            raise ValueError("Invalid landmark masks")
        t = f.get('t')
        if not isinstance(t, (int, float)) or not math.isfinite(t) or t <= last:
            raise ValueError("Frame times must be finite and strictly increasing")
        last = t
    if len(frames) > 1 and not 0 < frames[-1]['t'] - frames[0]['t'] <= 12:
        raise ValueError("A gesture clip cannot be longer than 12 seconds.")
    return frames


def coverage(frames):
    return float(np.mean([f['body'] and all(f['valid']) for f in frames]))


def trim_active(frames):
    """Remove inactive lead-in/out only; never fill gaps inside the action."""
    active = [i for i, f in enumerate(frames) if f['body'] and all(f['valid'])]
    if len(active) < 2:
        return frames
    return frames[active[0]:active[-1] + 1]


def resample(frames, count=24):
    times = np.array([f['t'] for f in frames])
    indices = np.abs(times[:, None] - np.linspace(times[0], times[-1], count)).argmin(axis=0)
    return [frames[i] for i in indices]


def motion(frames):
    good = [f for f in frames if f['body'] and all(f['valid'])]
    if len(good) < 3:
        return 0.0
    # Both handshape and body-relative wrist movement matter.
    return float(max(np.std([f['wrists'] for f in good], axis=0).mean(),
                     np.std([f['shape'] for f in good], axis=0).mean()))


def dtw_distance(left, right):
    """Average local cost on a constrained, monotonic DTW path; not a probability."""
    a, b = resample(left), resample(right)
    sa, sb = np.array([x['shape'] for x in a]), np.array([x['shape'] for x in b])
    wa, wb = np.array([x['wrists'] for x in a]), np.array([x['wrists'] for x in b])
    va, vb = np.array([x['valid'] for x in a]), np.array([x['valid'] for x in b])
    common = va[:, None, :] & vb[None, :, :]
    hand_cost = np.sqrt(np.mean((sa[:, None] - sb[None, :]) ** 2, axis=-1))
    body_cost = np.sqrt(np.mean((wa[:, None] - wb[None, :]) ** 2, axis=-1))
    costs = np.mean(np.where(common, .65 * hand_cost + .35 * body_cost, .8), axis=-1)
    body_ok = np.array([x['body'] for x in a])[:, None] & np.array([x['body'] for x in b])[None, :]
    costs += np.where(body_ok, 0, .4)
    n, m = costs.shape
    dp = np.full((n + 1, m + 1), np.inf)
    steps = np.zeros((n + 1, m + 1), dtype=int)
    dp[0, 0] = 0
    for i in range(1, n + 1):
        for j in range(max(1, i - 8), min(m, i + 8) + 1):
            p, q = min(((i-1, j-1), (i-1, j), (i, j-1)), key=lambda ij: dp[ij])
            dp[i, j] = dp[p, q] + costs[i-1, j-1]
            steps[i, j] = steps[p, q] + 1
    return float(dp[n, m] / max(1, steps[n, m]))


class TemplateBank:
    def __init__(self, directory: Path, threshold=.4, margin=.8):
        if not 0 < threshold < 5 or not 0 < margin < 1:
            raise ValueError("Invalid DTW threshold/margin")
        self.directory, self.threshold, self.margin = directory, threshold, margin
        self.items = []
        self.reload()

    def reload(self):
        items = []
        for path in sorted(self.directory.glob('*.json')):
            item = json.loads(path.read_text())
            if item.get('version') != VERSION or item.get('label') not in ('cup', 'negative') or item.get('split') not in ('template', 'test'):
                raise ValueError(f"Invalid template: {path.name}")
            validate_frames(item['frames'])
            items.append(item)
        self.items = items

    def summary(self):
        return {f'{split}_{label}': sum(x['split'] == split and x['label'] == label for x in self.items)
                for split in ('template', 'test') for label in ('cup', 'negative')}

    def save(self, frames, label, split, name='', source=None):
        validate_frames(frames)
        if label not in ('cup', 'negative') or split not in ('template', 'test'):
            raise ValueError('Invalid label/split')
        if len(self.items) >= 200:
            raise ValueError('The library already has 200 samples. Remove some before adding more.')
        if split == 'template':
            frames = trim_active(frames)
            validate_frames(frames)
        if split == 'template' and label == 'cup' and (coverage(frames) < .65 or motion(frames) < .015):
            raise ValueError('A target-gesture template needs clear hands, shoulders, and visible motion. Adjust the framing and record it again.')
        name = str(name).strip()[:100] or label
        item = dict(version=VERSION, id=uuid4().hex, label=label, split=split, name=name,
                    source=source or {'kind': 'local_camera', 'asl_reviewed': False}, frames=frames)
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / f"{item['id']}.json"
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(item, ensure_ascii=False, allow_nan=False))
        temporary.replace(path)
        self.items.append(item)
        return {k: v for k, v in item.items() if k != 'frames'}

    def match(self, frames):
        validate_frames(frames)
        frames = trim_active(frames)
        result = dict(gloss='unclear', reason='quality', cup_distance=None, negative_distance=None,
                      threshold=self.threshold, margin=self.margin, coverage=round(coverage(frames), 3))
        if len(frames) < 8 or coverage(frames) < .65:
            return result
        if motion(frames) < .015:
            return dict(result, reason='no_motion')
        positives = [x for x in self.items if x['split'] == 'template' and x['label'] == 'cup']
        negatives = [x for x in self.items if x['split'] == 'template' and x['label'] == 'negative']
        if not positives or not negatives:
            return dict(result, reason='need_templates')
        scores = [(dtw_distance(frames, x['frames']), x) for x in positives]
        pos, item = min(scores, key=lambda x: x[0])
        neg = min(dtw_distance(frames, x['frames']) for x in negatives)
        accepted = pos <= self.threshold and pos < neg * self.margin
        return dict(result, gloss='cup' if accepted else 'unclear', reason='matched' if accepted else 'no_match',
                    cup_distance=round(pos, 4), negative_distance=round(neg, 4), template_name=item['name'])


class TriggerGate:
    """Two positive observations; rearm only after >=0.8s with no hands."""
    def __init__(self):
        self.latched = False
        self.hits = 0
        self.last_hit = -math.inf
        self.neutral_since = None
        self.fired_at = -math.inf

    def observe(self, neutral, now):
        if neutral:
            if self.neutral_since is None:
                self.neutral_since = now
            self.hits = 0
        else:
            self.neutral_since = None
        if self.latched and self.neutral_since is not None and now - self.neutral_since >= .8 and now - self.fired_at >= 1.5:
            self.latched = False
            return True
        return False

    def match(self, accepted, now):
        if self.latched:
            return None
        if not accepted:
            self.hits = 0
            return None
        self.hits = self.hits + 1 if now - self.last_hit <= 1.5 else 1
        self.last_hit = now
        if self.hits >= 2:
            self.latched, self.fired_at, self.hits = True, now, 0
            return str(uuid4())
        return None
