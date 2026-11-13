"""Serve a loopback-only webcam recognition page and local I3D inference."""

import base64
import json
import math
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
import time
from uuid import uuid4


def add_command(commands) -> None:
    parser = commands.add_parser("camera", help="Open local webcam sign recognition")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--backend", choices=("landmarks", "i3d"), default="landmarks")
    parser.add_argument("--model-dir", type=Path)
    parser.add_argument("--templates-dir", type=Path, default=Path("data/cup-templates"))
    parser.add_argument("--distance-threshold", type=float, default=0.4)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--robot-config", type=Path, help="Arm profile that receives request_cup")
    parser.add_argument("--no-robot", action="store_true", help="Recognize signs without sending a robot request")


def run(args) -> None:
    if args.backend == "landmarks":
        from gesture_aid.perception.landmark_camera import run as run_landmarks
        return run_landmarks(args)
    import cv2
    import numpy as np

    from gesture_aid.perception.i3d import I3DRecognizer
    from gesture_aid.perception.wlasl import request_from_gloss

    if not 1 <= args.port <= 65535:
        raise ValueError("Port must be between 1 and 65535.")
    if not math.isfinite(args.threshold) or not 0 < args.threshold <= 1:
        raise ValueError("Threshold must be greater than zero and at most one.")
    project = args.project.resolve()
    model_dir = (args.model_dir or project / "models/wlasl-i3d").resolve()
    recognizer = I3DRecognizer(project, model_dir)
    lexicon = project / "configs/sign_lexicon.json"
    page = (Path(__file__).parent.parent / "dashboard/camera.html").read_bytes()
    inference_lock = Lock()
    allowed_hosts = {f"localhost:{args.port}", f"127.0.0.1:{args.port}"}

    class Handler(BaseHTTPRequestHandler):
        def reply(self, status, payload, content_type="application/json"):
            body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.headers.get("Host") not in allowed_hosts:
                self.reply(403, {"error": "Local access only."})
            elif self.path == "/":
                self.reply(200, page, "text/html; charset=utf-8")
            elif self.path == "/health":
                self.reply(200, {"status": "ok", "model": "WLASL2000 I3D", "threshold": args.threshold})
            else:
                self.reply(404, {"error": "Not found."})

        def do_POST(self):
            origin = self.headers.get("Origin")
            if self.headers.get("Host") not in allowed_hosts or (
                origin is not None and origin not in {f"http://{host}" for host in allowed_hosts}
            ):
                self.reply(403, {"error": "Local access only."})
                return
            if self.path != "/recognize":
                self.reply(404, {"error": "Not found."})
                return
            if self.headers.get_content_type() != "application/json":
                self.reply(415, {"error": "Expected application/json."})
                return
            if not inference_lock.acquire(blocking=False):
                self.reply(409, {"error": "Recognizer is busy. Try the next clip."})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 8 * 1024 * 1024:
                    raise ValueError("Clip payload must be at most 8 MB.")
                self.connection.settimeout(15)
                data = json.loads(self.rfile.read(length))
                encoded_frames = data.get("frames")
                if not isinstance(encoded_frames, list) or not 16 <= len(encoded_frames) <= 64:
                    raise ValueError("Provide 16 to 64 JPEG frames.")
                frames = []
                for encoded in encoded_frames:
                    image = cv2.imdecode(np.frombuffer(base64.b64decode(encoded, validate=True), dtype=np.uint8), cv2.IMREAD_COLOR)
                    if image is None or image.shape != (256, 256, 3):
                        raise ValueError("Each frame must be a 256 by 256 JPEG image.")
                    frames.append(image)
                started = time.monotonic()
                predictions = recognizer.predict(frames)
                best = predictions[0]
                gloss = best["gloss"] if best["score"] >= args.threshold else "unclear"
                request = request_from_gloss(gloss, lexicon, request_id=str(uuid4()))
                if request.intent.value == "unclear":
                    gloss = "unclear"
                self.reply(200, {
                    "gloss": gloss,
                    "score": best["score"],
                    "predictions": predictions,
                    "intent": request.intent.value,
                    "seconds": round(time.monotonic() - started, 2),
                    "threshold": args.threshold,
                    "robot_connected": False,
                })
            except (ValueError, TypeError, AttributeError) as error:
                self.reply(400, {"error": str(error)})
            except Exception as error:
                self.reply(500, {"error": str(error)})
            finally:
                inference_lock.release()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Camera recognition ready at http://localhost:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
