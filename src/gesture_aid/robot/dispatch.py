"""Forward one recognized intent to the arm without blocking the camera."""

from threading import Lock, Thread
from uuid import uuid4

from gesture_aid.contracts import Intent


def _start_daemon(target, args) -> None:
    Thread(target=target, args=args, daemon=True).start()


class ArmRequestSender:
    """Send `request_cup` to MakerMods while the recognizer keeps streaming.

    A second sign that arrives while the arm is still moving is refused.
    Finishing the rollout does not claim the object was delivered.
    """

    def __init__(self, robot, spawn=None) -> None:
        self.robot = robot
        self._spawn = spawn or _start_daemon
        self._lock = Lock()
        self.busy = False
        self.last_error: str | None = None
        self.last_request_id: str | None = None

    def submit(self, intent: str) -> bool:
        with self._lock:
            if self.busy:
                self.last_error = "The arm is still running the previous request."
                return False
            self.busy = True
            self.last_error = None
            self.last_request_id = str(uuid4())
            request_id = self.last_request_id
        self._spawn(self._run, (intent, request_id))
        return True

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "robot_connected": True,
                "robot_busy": self.busy,
                "request_id": self.last_request_id,
                "request_error": self.last_error,
            }

    def _run(self, intent: str, request_id: str) -> None:
        try:
            self.robot.execute(Intent(intent))
        except Exception as error:
            print(f"{intent} failed: {error}", flush=True)
            with self._lock:
                if self.last_request_id == request_id:
                    self.last_error = str(error)
        finally:
            with self._lock:
                if self.last_request_id == request_id:
                    self.busy = False
