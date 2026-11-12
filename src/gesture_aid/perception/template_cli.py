"""Download landmark models, import WLASL clips and evaluate held-out samples."""
from pathlib import Path
import hashlib
import json
import urllib.request

MODEL_URLS = {
    'hand_landmarker.task': 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task',
    'pose_landmarker_lite.task': 'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task',
}


def add_commands(commands):
    parser = commands.add_parser('templates', help='MediaPipe CUP template tools')
    parser.add_argument('--directory', type=Path, default=Path('data/cup-templates'))
    parser.add_argument('--model-dir', type=Path, default=Path('models/mediapipe'))
    sub = parser.add_subparsers(dest='template_command', required=True)
    sub.add_parser('setup', help='Download official MediaPipe models')
    sub.add_parser('stats')
    evaluate = sub.add_parser('evaluate', help='Evaluate test samples excluded from templates')
    evaluate.add_argument('--threshold', type=float, default=.4)
    video = sub.add_parser('import-video', help='Import a previously trimmed, unmirrored action clip')
    video.add_argument('video', type=Path)
    video.add_argument('--label', choices=('cup','negative'), required=True)
    video.add_argument('--split', choices=('template','test'), default='template')
    video.add_argument('--name', default='')
    wlasl = sub.add_parser('import-wlasl', help='Import prepared WLASL clips, optionally download direct MP4 sources')
    wlasl.add_argument('--annotations', type=Path, default=Path('third_party/WLASL/start_kit/WLASL_v0.3.json'))
    wlasl.add_argument('--videos-dir', type=Path, default=Path('data/wlasl/videos'))
    wlasl.add_argument('--gloss', default='cup')
    wlasl.add_argument('--label', choices=('cup','negative'), default='cup')
    wlasl.add_argument('--download', action='store_true')


def download(url, path, maximum):
    request = urllib.request.Request(url, headers={'User-Agent':'SignAid research prototype'})
    with urllib.request.urlopen(request, timeout=15) as response:
        data = response.read(maximum + 1)
    if len(data) > maximum:
        raise ValueError('Download exceeds size limit')
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_bytes(data)
    temporary.replace(path)
    return hashlib.sha256(data).hexdigest()


def video_features(path, extractor):
    import cv2
    cap = cv2.VideoCapture(str(path))
    try:
        fps, count = cap.get(cv2.CAP_PROP_FPS), int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if not cap.isOpened() or not 1 <= fps <= 240 or not 0 < count / fps <= 12:
            raise ValueError('需要可解码的、已截取完整单次动作的短视频（不超过 12 秒）。')
        frames, index, next_time = [], 0, 0.
        while True:
            ok, bgr = cap.read()
            if not ok:
                break
            t = index / fps
            index += 1
            if t + 1e-6 < next_time:
                continue
            ratio = min(1., 640 / max(bgr.shape[:2]))
            if ratio < 1:
                bgr = cv2.resize(bgr, (round(bgr.shape[1] * ratio), round(bgr.shape[0] * ratio)))
            feature, _ = extractor.extract(bgr, t)
            frames.append(feature)
            next_time += .125
        return frames
    finally:
        cap.release()


def run(args):
    if args.template_command == 'setup':
        provenance = []
        for filename, url in MODEL_URLS.items():
            path = args.model_dir / filename
            digest = download(url, path, 32 * 1024 * 1024)
            provenance.append(dict(file=filename, url=url, sha256=digest))
        (args.model_dir / 'provenance.json').write_text(json.dumps(provenance, indent=2))
        return {'models':provenance}
    from .templates import TemplateBank
    bank = TemplateBank(args.directory, getattr(args, 'threshold', .4))
    if args.template_command == 'stats':
        return bank.summary()
    if args.template_command == 'evaluate':
        samples = [x for x in bank.items if x['split'] == 'test']
        rows = [dict(id=x['id'], name=x['name'], expected=x['label'], **bank.match(x['frames'])) for x in samples]
        positives = [x for x in rows if x['expected']=='cup']
        negatives = [x for x in rows if x['expected']=='negative']
        ready = all(bank.summary()[f'template_{label}'] for label in ('cup','negative'))
        return dict(templates=bank.summary(), threshold=bank.threshold, calibrated=False,
                    note='Clip classification only; evaluate live false triggers separately. Do not tune on this test set.',
                    recall=sum(x['gloss']=='cup' for x in positives)/len(positives) if positives and ready else None,
                    false_positive_rate=sum(x['gloss']=='cup' for x in negatives)/len(negatives) if negatives and ready else None,
                    samples=rows)
    from .landmarks import LandmarkExtractor
    extractor = LandmarkExtractor(args.model_dir)
    try:
        if args.template_command == 'import-video':
            return bank.save(video_features(args.video, extractor), args.label, args.split, args.name,
                             {'kind':'local_video','file':args.video.name,'asl_reviewed':False})
        entries = json.loads(args.annotations.read_text())
        entry = next((x for x in entries if x['gloss'] == args.gloss), None)
        if entry is None:
            raise ValueError('Unknown WLASL gloss')
        if (args.gloss == 'cup') != (args.label == 'cup'):
            raise ValueError('Only WLASL cup may be labeled cup; other glosses must be negative')
        report = []
        from urllib.parse import urlparse
        for sample in entry['instances']:
            vid = sample['video_id']
            source = dict(kind='WLASL', gloss=args.gloss, video_id=vid, signer_id=sample['signer_id'],
                          original_split=sample['split'], url=sample['url'], asl_reviewed=False)
            if any(x['source'].get('kind') == 'WLASL' and x['source'].get('video_id') == vid for x in bank.items):
                report.append(dict(video_id=vid, status='already_imported'))
                continue
            path = args.videos_dir / f'{vid}.mp4'
            try:
                if not path.exists() and args.download:
                    # Direct single-gloss videos only. Compilation URLs require upstream preprocessing.
                    url = sample['url']
                    if urlparse(url).path.lower().endswith('.mp4') and sample['frame_start']==1 and sample['frame_end']==-1:
                        source['sha256'] = download(url, path, 30 * 1024 * 1024)
                if not path.exists():
                    report.append(dict(video_id=vid, status='missing', url=sample['url']))
                    continue
                source.setdefault('sha256', hashlib.sha256(path.read_bytes()).hexdigest())
                frames = video_features(path, extractor)
                split = 'template' if sample['split']=='train' else 'test'
                item = bank.save(frames, args.label, split, f'WLASL {args.gloss} {vid}', source)
                report.append(dict(video_id=vid, status='imported', split=split, id=item['id']))
            except Exception as error:
                report.append(dict(video_id=vid, status='failed', error=str(error)))
        args.directory.mkdir(parents=True, exist_ok=True)
        # Report is outside the template glob; templates have one strict schema.
        report_path = args.directory / 'reports' / f'wlasl-{args.gloss}.json'
        report_path.parent.mkdir(exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        return dict(counts=bank.summary(), results=report)
    finally:
        extractor.close()
