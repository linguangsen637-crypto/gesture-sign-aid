"""Check confirmation, request identity, and independent delivery reporting."""

import unittest

from gesture_aid.contracts import Intent, RetrievalRequest, Status
from gesture_aid.robot.mock import MockRobot
from gesture_aid.workflow.controller import RetrievalWorkflow


class WorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.robot = MockRobot()
        self.workflow = RetrievalWorkflow(self.robot)
        self.request = RetrievalRequest("test-1", Intent.WATER, "test-sign")

    def test_confirmation_and_delivery_are_separate(self) -> None:
        self.workflow.submit(self.request)
        self.assertEqual(self.robot.executed_skills, [])
        self.workflow.confirm(self.request.request_id)
        self.assertEqual(self.robot.executed_skills, ["pick_water"])
        self.assertEqual(self.workflow.status, Status.WAITING_RESULT)
        self.workflow.record_result(self.request.request_id, delivered=True)
        self.assertEqual(self.workflow.status, Status.COMPLETED)

    def test_unclear_request_keeps_waiting(self) -> None:
        self.workflow.submit(RetrievalRequest("unclear-1", Intent.UNCLEAR, "test-sign"))
        self.assertEqual(self.workflow.status, Status.IDLE)
        self.assertEqual(self.robot.executed_skills, [])

    def test_stale_confirmation_is_rejected(self) -> None:
        self.workflow.submit(self.request)
        with self.assertRaises(ValueError):
            self.workflow.confirm("different-request")
        self.assertEqual(self.robot.executed_skills, [])

    def test_cancelled_request_cannot_execute_or_replay(self) -> None:
        self.workflow.submit(self.request)
        self.workflow.cancel(self.request.request_id)
        with self.assertRaises(RuntimeError):
            self.workflow.confirm(self.request.request_id)
        self.workflow.reset()
        with self.assertRaises(ValueError):
            self.workflow.submit(self.request)

    def test_active_request_cannot_be_overwritten_or_reset(self) -> None:
        self.workflow.submit(self.request)
        with self.assertRaises(RuntimeError):
            self.workflow.submit(RetrievalRequest("test-2", Intent.TISSUE, "test-sign"))
        with self.assertRaises(RuntimeError):
            self.workflow.reset()

    def test_executor_failure_remains_failed(self) -> None:
        class FailingRobot:
            def execute(self, intent: Intent) -> None:
                raise RuntimeError("execution failed")

        workflow = RetrievalWorkflow(FailingRobot())
        workflow.submit(self.request)
        with self.assertRaisesRegex(RuntimeError, "execution failed"):
            workflow.confirm(self.request.request_id)
        self.assertEqual(workflow.status, Status.FAILED)
        self.assertEqual(workflow.error, "execution failed")

    def test_unconfirmed_delivery_is_failed(self) -> None:
        self.workflow.submit(self.request)
        self.workflow.confirm(self.request.request_id)
        self.workflow.record_result(self.request.request_id, delivered=False)
        self.assertEqual(self.workflow.status, Status.FAILED)


if __name__ == "__main__":
    unittest.main()
