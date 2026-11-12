"""Automatically execute one accepted request at a time."""

from threading import Lock

from gesture_aid.contracts import Intent, RetrievalRequest, Status
from gesture_aid.robot.base import RobotExecutor


class RetrievalWorkflow:
    def __init__(self, robot: RobotExecutor) -> None:
        self.robot = robot
        self.status = Status.IDLE
        self.request: RetrievalRequest | None = None
        self.error: str | None = None
        self._seen_request_ids: set[str] = set()
        self._lock = Lock()

    def submit(self, request: RetrievalRequest) -> None:
        with self._lock:
            if self.status != Status.IDLE:
                raise RuntimeError("Finish the current request before submitting another.")
            if request.request_id in self._seen_request_ids:
                raise ValueError("Duplicate request identifier.")
            self._seen_request_ids.add(request.request_id)
            if request.intent == Intent.UNCLEAR:
                return
            self.request = request
            self.status = Status.EXECUTING
        try:
            self.robot.execute(request.intent)
        except Exception as error:
            with self._lock:
                self.error = str(error)
                self.status = Status.FAILED
            raise
        with self._lock:
            self.status = Status.WAITING_RESULT

    def record_result(self, request_id: str, *, delivered: bool) -> None:
        with self._lock:
            self._require(Status.WAITING_RESULT, request_id)
            self.status = Status.COMPLETED if delivered else Status.FAILED
            self.error = None if delivered else "Delivery was not confirmed."

    def reset(self) -> None:
        with self._lock:
            if self.status not in {Status.COMPLETED, Status.FAILED}:
                raise RuntimeError("Reset requires a completed or failed request.")
            self.request = None
            self.error = None
            self.status = Status.IDLE

    def _require(self, status: Status, request_id: str) -> None:
        if self.status != status:
            raise RuntimeError(f"Expected {status}, found {self.status}.")
        if self.request is None or self.request.request_id != request_id:
            raise ValueError("Request identifier does not match the active request.")
