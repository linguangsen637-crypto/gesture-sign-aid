"""Map WLASL word labels supplied by a recognizer into retrieval requests."""

import json
from pathlib import Path
from uuid import uuid4

from gesture_aid.contracts import Intent, RetrievalRequest


def request_from_gloss(
    gloss: str,
    lexicon: Path = Path("configs/sign_lexicon.json"),
    *,
    request_id: str | None = None,
) -> RetrievalRequest:
    """Use a stable request_id for retries of the same recognized action clip."""
    config = json.loads(lexicon.read_text(encoding="utf-8"))
    normalized = gloss.strip().lower()
    intents = {entry["gloss"]: Intent(entry["intent"]) for entry in config["entries"]}
    return RetrievalRequest(
        request_id=str(uuid4()) if request_id is None else request_id,
        intent=intents.get(normalized, Intent.UNCLEAR),
        recognized_sign_id=f"wlasl:{normalized or 'unknown'}",
    )
