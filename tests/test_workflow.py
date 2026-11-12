"""Check automatic execution, request identity, and delivery reporting."""

import unittest
from threading import Event, Thread

from gesture_aid.contracts import Intent, RetrievalRequest, Status
from gesture_aid.robot.mock import MockRobot
from gesture_aid.workflow.controller import RetrievalWorkflow


class WorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.robot = MockRobot()
        self.workflow = RetrievalWorkflow(self.robot)
        self.request = RetrievalRequest("test-1", Intent.CUP, "test-sign")

    def test_submit_executes_cup_and_waits_for_delivery_report(self) -> None:
        self.workflow.submit(self.request)
        self.assertEqual(self.robot.executed_skills, ["pick_cup"])
        self.assertEqual(self.workflow.status, Status.WAITING_RESULT)
        self.workflow.record_result(self.request.request_id, delivered=True)
        self.assertEqual(self.workflow.status, Status.COMPLETED)

    def test_unclear_request_keeps_waiting(self) -> None:
        self.workflow.submit(RetrievalRequest("unclear-1", Intent.UNCLEAR, "test-sign"))
        self.assertEqual(self.workflow.status, Status.IDLE)
        self.assertEqual(self.robot.executed_skills, [])

    def test_stale_delivery_report_is_rejected(self) -> None:
        self.workflow.submit(self.request)
        with self.assertRaises(ValueError):
            self.workflow.record_result("different-request", delivered=True)
        self.assertEqual(self.workflow.status, Status.WAITING_RESULT)

    def test_completed_request_cannot_replay_after_reset(self) -> None:
        self.workflow.submit(self.request)
        self.workflow.record_result(self.request.request_id, delivered=True)
        self.workflow.reset()
        with self.assertRaises(ValueError):
            self.workflow.submit(self.request)
        self.assertEqual(self.robot.executed_skills, ["pick_cup"])
        self.workflow.submit(RetrievalRequest("next-cup", Intent.CUP, "test-sign"))
        self.assertEqual(self.robot.executed_skills, ["pick_cup", "pick_cup"])

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
        with self.assertRaisesRegex(RuntimeError, "execution failed"):
            workflow.submit(self.request)
        self.assertEqual(workflow.status, Status.FAILED)
        self.assertEqual(workflow.error, "execution failed")
        workflow.reset()
        self.assertIsNone(workflow.error)
        with self.assertRaises(ValueError):
            workflow.submit(self.request)

    def test_unconfirmed_delivery_is_failed(self) -> None:
        self.workflow.submit(self.request)
        self.workflow.record_result(self.request.request_id, delivered=False)
        self.assertEqual(self.workflow.status, Status.FAILED)

    def test_running_executor_rejects_concurrent_request_and_reset(self) -> None:
        started = Event()
        release = Event()
        calls = []
        errors = []

        class BlockingRobot:
            def execute(self, intent: Intent) -> None:
                calls.append(intent)
                started.set()
                if not release.wait(timeout=5):
                    raise RuntimeError("test executor timed out")

        workflow = RetrievalWorkflow(BlockingRobot())

        def submit() -> None:
            try:
                workflow.submit(self.request)
            except Exception as error:
                errors.append(error)

        thread = Thread(target=submit)
        thread.start()
        try:
            self.assertTrue(started.wait(timeout=5))
            self.assertEqual(workflow.status, Status.EXECUTING)
            with self.assertRaises(RuntimeError):
                workflow.submit(RetrievalRequest("test-2", Intent.CUP, "test-sign"))
            with self.assertRaises(RuntimeError):
                workflow.reset()
        finally:
            release.set()
            thread.join(timeout=5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(calls, [Intent.CUP])
        self.assertEqual(workflow.status, Status.WAITING_RESULT)


if __name__ == "__main__":
    unittest.main()
