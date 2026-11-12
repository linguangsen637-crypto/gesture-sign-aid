"""Local-only MediaPipe streaming API. Never imports or invokes a robot executor."""
import base64
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Lock
import time
from uuid import UUID

import cv2
import numpy as np

from .landmarks import LandmarkExtractor
from .templates import TemplateBank, TriggerGate


class CameraApp:
    def __init__(self, extractor, bank):
        self.extractor, self.bank = extractor, bank
        self.lock = Lock()
        self.sessions = {}

    def health(self):
        return dict(status='ok', model='MediaPipe Hands + Pose / DTW', templates=self.bank.summary(),
                    threshold=self.bank.threshold, calibrated=False, robot_connected=False)

    def frame(self, data):
        session_id = str(UUID(data['session_id']))
        timestamp = float(data['timestamp'])
        if not np.isfinite(timestamp) or not 0 <= timestamp <= 1e12:
            raise ValueError('Invalid timestamp')
        encoded = data['image']
        if not isinstance(encoded, str) or len(encoded) > 700000:
            raise ValueError('Frame too large')
        bgr = cv2.imdecode(np.frombuffer(base64.b64decode(encoded, validate=True), dtype=np.uint8), cv2.IMREAD_COLOR)
        if bgr is None or not 120 <= min(bgr.shape[:2]) or max(bgr.shape[:2]) > 960:
            raise ValueError('Frame dimensions must be 120–960 pixels')
        now = time.monotonic()
        self.sessions = {k: v for k, v in self.sessions.items() if now - v['seen'] < 300}
        if session_id not in self.sessions:
            if len(self.sessions) >= 8:
                raise ValueError('Too many camera sessions; close other pages and wait five minutes')
            self.sessions[session_id] = dict(seen=now, timestamp=-1., frames=deque(maxlen=64), gate=TriggerGate(), checked=0., result={'gloss':'unclear','reason':'warming_up'})
        s = self.sessions[session_id]
        if timestamp <= s['timestamp']:
            raise ValueError('Stale frame')
        if timestamp - s['timestamp'] > .75:
            s['frames'].clear()
            s['gate'].hits = 0
            s['gate'].neutral_since = None
            s['result'] = {'gloss':'unclear','reason':'warming_up'}
        s['timestamp'], s['seen'] = timestamp, now
        feature, overlay = self.extractor.extract(bgr, timestamp)
        neutral = not any(feature['valid'])
        rearmed = s['gate'].observe(neutral, now)
        if rearmed or neutral or data.get('recording') is True:
            s['frames'].clear()
            s['result'] = {'gloss':'unclear','reason':'recording' if data.get('recording') is True else 'no_hands'}
            s['gate'].hits = 0
        else:
            s['frames'].append(feature)
            if len(s['frames']) < 8:
                s['result'] = {'gloss':'unclear','reason':'warming_up'}
        event = None
        if now - s['checked'] >= .1 and len(s['frames']) >= 8 and not s['gate'].latched:
            s['checked'] = now
            results = []
            for duration in (1.5, 2.5, 3.5):
                clip = [f for f in s['frames'] if timestamp - f['t'] <= duration]
                if len(clip) >= 8 and clip[-1]['t'] - clip[0]['t'] >= .75:
                    results.append(self.bank.match(clip))
            if results:
                # Prefer a qualifying full-sequence match, otherwise show nearest diagnostic.
                s['result'] = min(results, key=lambda r: (r['gloss'] != 'cup', r.get('cup_distance') if r.get('cup_distance') is not None else 999))
                event = s['gate'].match(s['result']['gloss'] == 'cup', now)
        return dict(feature=feature, overlay=overlay, match=s['result'], latched=s['gate'].latched,
                    event_id=event, intent='request_cup' if event else 'unclear', robot_connected=False,
                    templates=self.bank.summary())


def handler_for(app):
    page = (Path(__file__).parent.parent / 'dashboard/landmarks.html').read_bytes()

    class Handler(BaseHTTPRequestHandler):
        def reply(self, status, payload, content_type='application/json'):
            body = payload if isinstance(payload, bytes) else json.dumps(payload, allow_nan=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; media-src 'self' blob:; img-src 'self' data:; frame-ancestors 'none'")
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def local(self):
            hosts = {f'localhost:{self.server.server_port}', f'127.0.0.1:{self.server.server_port}'}
            origin = self.headers.get('Origin')
            return self.headers.get('Host') in hosts and (origin is None or origin in {f'http://{h}' for h in hosts})

        def do_GET(self):
            if not self.local():
                self.reply(403, {'error':'Local access only'})
                return
            if self.path == '/':
                self.reply(200, page, 'text/html; charset=utf-8')
            elif self.path == '/health':
                with app.lock:
                    self.reply(200, app.health())
            else:
                self.reply(404, {'error':'Not found'})

        def do_POST(self):
            if not self.local():
                self.reply(403, {'error':'Local access only'})
                return
            if self.path not in ('/frame', '/templates'):
                self.reply(404, {'error':'Not found'})
                return
            if self.headers.get_content_type() != 'application/json':
                self.reply(415, {'error':'Expected JSON'})
                return
            if not app.lock.acquire(blocking=False):
                self.reply(409, {'error':'模型正在处理另一请求，请稍后重试。'})
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 2 * 1024 * 1024:
                    raise ValueError('Invalid request size')
                self.connection.settimeout(10)
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError('Expected object')
                if self.path == '/frame':
                    result = app.frame(data)
                else:
                    item = app.bank.save(data['frames'], data['label'], data['split'], data.get('name',''))
                    result = dict(saved=item, templates=app.bank.summary(), robot_connected=False)
                    for s in app.sessions.values():
                        s['frames'].clear()
                        s['gate'].hits = 0
                self.reply(200, result)
            except (ValueError, TypeError, KeyError, OverflowError) as error:
                self.reply(400, {'error':str(error)})
            except Exception as error:
                self.reply(500, {'error':str(error)})
            finally:
                app.lock.release()
    return Handler


def run(args):
    if not 1 <= args.port <= 65535:
        raise ValueError('Invalid port')
    project = args.project.resolve()
    def resolve(path):
        return path if path.is_absolute() else project / path
    model_dir = resolve(args.model_dir or Path('models/mediapipe'))
    bank = TemplateBank(resolve(args.templates_dir), args.distance_threshold)
    extractor = LandmarkExtractor(model_dir)
    try:
        server = ThreadingHTTPServer(('127.0.0.1', args.port), handler_for(CameraApp(extractor, bank)))
        print(f'MediaPipe CUP recognition ready at http://localhost:{args.port}', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
    finally:
        extractor.close()
