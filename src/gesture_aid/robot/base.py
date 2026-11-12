"""Contract for execution adapters."""

from typing import Protocol

from gesture_aid.contracts import Intent


class RobotExecutor(Protocol):
    def execute(self, intent: Intent) -> None:
        """Return after execution ends, or raise on failure.

        Physical adapters must own their motor lifecycle and stop handling.
        Return does not establish that an item was delivered.
        """
        ...
