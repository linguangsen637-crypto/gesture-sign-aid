"""Shared request types used by perception, workflow, and robot modules."""

from dataclasses import dataclass
from enum import StrEnum


class Intent(StrEnum):
    CUP = "request_cup"
    WATER = "request_water"
    TISSUE = "request_tissue"
    UNCLEAR = "unclear"


class Status(StrEnum):
    IDLE = "idle"
    EXECUTING = "executing"
    WAITING_RESULT = "waiting_result"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class RetrievalRequest:
    request_id: str
    intent: Intent
    recognized_sign_id: str

    def __post_init__(self) -> None:
        if not self.request_id.strip() or not self.recognized_sign_id.strip():
            raise ValueError("Request and sign identifiers must be nonempty.")
        if not isinstance(self.intent, Intent):
            raise ValueError("intent must be a supported Intent value.")
