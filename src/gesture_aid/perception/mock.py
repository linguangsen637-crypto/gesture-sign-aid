"""Generate explicitly simulated recognition requests for integration work."""

from uuid import uuid4

from gesture_aid.contracts import Intent, RetrievalRequest


def simulate_recognition(intent: Intent) -> RetrievalRequest:
    return RetrievalRequest(
        request_id=str(uuid4()),
        intent=intent,
        recognized_sign_id="simulation_only",
    )
