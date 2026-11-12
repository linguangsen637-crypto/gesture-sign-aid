"""In-memory skill execution for development without robot hardware."""

from gesture_aid.contracts import Intent


class MockRobot:
    def __init__(self) -> None:
        self.executed_skills: list[str] = []

    def execute(self, intent: Intent) -> None:
        skills = {
            Intent.CUP: "pick_cup",
            Intent.WATER: "pick_water",
            Intent.TISSUE: "pick_tissue",
        }
        if intent not in skills:
            raise ValueError("No retrieval skill for this intent.")
        self.executed_skills.append(skills[intent])
