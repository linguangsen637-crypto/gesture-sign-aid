"""The camera can hand one intent to the arm without waiting for the rollout."""

import time
import unittest

from gesture_aid.contracts import Intent
from gesture_aid.robot.dispatch import ArmRequestSender


class Robot:
    def __init__(self, error=None):
        self.calls = []
        self.error = error

    def execute(self, intent):
        self.calls.append(intent)
        if self.error:
            raise RuntimeError(self.error)


class DispatchTests(unittest.TestCase):
    def test_the_real_background_thread_runs_the_intent(self):
        robot = Robot()
        sender = ArmRequestSender(robot)
        self.assertTrue(sender.submit("request_cup"))
        for _ in range(50):
            if robot.calls and not sender.snapshot()["robot_busy"]:
                break
            time.sleep(0.01)
        self.assertEqual(robot.calls, [Intent.CUP])
        self.assertFalse(sender.snapshot()["robot_busy"])

    def test_submit_runs_the_intent_once(self):
        robot = Robot()
        sender = ArmRequestSender(robot, spawn=lambda target, args: target(*args))
        self.assertTrue(sender.submit("request_cup"))
        self.assertEqual(robot.calls, [Intent.CUP])
        self.assertFalse(sender.snapshot()["robot_busy"])
        self.assertIsNone(sender.snapshot()["request_error"])

    def test_a_second_sign_is_refused_while_the_arm_is_moving(self):
        robot = Robot()
        started = {}

        def spawn(target, args):
            started["call"] = (target, args)

        sender = ArmRequestSender(robot, spawn=spawn)
        self.assertTrue(sender.submit("request_cup"))
        self.assertFalse(sender.submit("request_cup"))
        self.assertEqual(robot.calls, [])
        self.assertIn("previous request", sender.snapshot()["request_error"])
        started["call"][0](*started["call"][1])
        self.assertEqual(robot.calls, [Intent.CUP])

    def test_execute_failure_is_visible_and_releases_the_arm(self):
        sender = ArmRequestSender(Robot("serial port busy"), spawn=lambda target, args: target(*args))
        sender.submit("request_cup")
        snap = sender.snapshot()
        self.assertFalse(snap["robot_busy"])
        self.assertEqual(snap["request_error"], "serial port busy")
