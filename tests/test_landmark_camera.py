"""Camera session regression checks using synthetic images, no hardware required."""
import base64
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

HAS_VISION = all(importlib.util.find_spec(p) is not None for p in ('cv2','numpy'))
if HAS_VISION:
    import cv2
    import numpy as np
    from gesture_aid.perception.landmark_camera import CameraApp
    from gesture_aid.perception.templates import TemplateBank


@unittest.skipUnless(HAS_VISION, 'Install landmarks extra for camera tests')
class CameraTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        class Extractor:
            def extract(self, image, timestamp):
                return dict(t=timestamp,shape=[[0.]*63]*2,wrists=[[0.,0.]]*2,valid=[False,False],body=False),dict(hands=[],shoulders=[])
        self.app=CameraApp(Extractor(),TemplateBank(Path(temp.name)))
        _,image=cv2.imencode('.jpg',np.zeros((240,320,3),dtype=np.uint8))
        self.data=dict(session_id=str(uuid4()),timestamp=100.,image=base64.b64encode(image).decode())

    def test_empty_frame_never_fabricates_cup_or_landmarks(self):
        r=self.app.frame(self.data)
        self.assertFalse(r['robot_connected'])
        self.assertIsNone(r['event_id'])
        self.assertEqual(r['overlay']['hands'],[])
        self.assertEqual(r['match']['reason'],'no_hands')

    def test_stale_frame_is_rejected_and_sessions_are_isolated(self):
        self.app.frame(self.data)
        with self.assertRaisesRegex(ValueError,'Stale'):self.app.frame(self.data)
        self.app.frame(dict(self.data,session_id=str(uuid4())))
        self.assertEqual(len(self.app.sessions),2)

    def test_invalid_image_timestamp_and_session(self):
        for update in [dict(image='no jpeg'),dict(timestamp=float('nan')),dict(session_id='../file')]:
            with self.assertRaises(ValueError):self.app.frame(dict(self.data,**update))

    def test_camera_gap_does_not_count_as_observed_neutral_time(self):
        with patch('gesture_aid.perception.landmark_camera.time.monotonic',return_value=10):
            self.app.frame(self.data)
        s=self.app.sessions[self.data['session_id']]
        s['gate'].latched=True;s['gate'].fired_at=1;s['gate'].neutral_since=10
        with patch('gesture_aid.perception.landmark_camera.time.monotonic',return_value=20):
            r=self.app.frame(dict(self.data,timestamp=110.))
        self.assertTrue(r['latched'])

    def test_recording_suppresses_matching(self):
        r=self.app.frame(dict(self.data,recording=True))
        self.assertEqual(r['match']['reason'],'recording')
        self.assertIsNone(r['event_id'])

    def test_short_live_sequence_triggers_once_before_hands_leave(self):
        class VisibleHands:
            def extract(self, image, timestamp):
                return dict(t=timestamp,shape=[[0.]*63]*2,wrists=[[0.,0.]]*2,valid=[True,True],body=True),dict(hands=[],shoulders=[])
        self.app.extractor=VisibleHands()
        events=[]
        with patch.object(self.app.bank, 'match', return_value={'gloss':'cup','reason':'matched','cup_distance':.1}):
            for i in range(16):
                now=100+i*.125
                with patch('gesture_aid.perception.landmark_camera.time.monotonic',return_value=now):
                    r=self.app.frame(dict(self.data,timestamp=now))
                if r['event_id']:events.append(r['event_id'])
                if i==8:self.assertTrue(r['latched'])
        self.assertEqual(len(events),1)

    def test_cup_event_sends_one_request_when_arm_is_attached(self):
        class VisibleHands:
            def extract(self, image, timestamp):
                return dict(t=timestamp,shape=[[0.]*63]*2,wrists=[[0.,0.]]*2,valid=[True,True],body=True),dict(hands=[],shoulders=[])
        class Sender:
            def __init__(self):
                self.intents=[]
            def submit(self, intent):
                self.intents.append(intent)
                return True
            def snapshot(self):
                return dict(robot_connected=True, robot_busy=False, request_id='req', request_error=None)
        self.app.extractor=VisibleHands()
        self.app.sender=Sender()
        self.app.settle=lambda: None
        sent=None
        with patch.object(self.app.bank, 'match', return_value={'gloss':'cup','reason':'matched','cup_distance':.1}):
            for i in range(16):
                now=100+i*.125
                with patch('gesture_aid.perception.landmark_camera.time.monotonic',return_value=now):
                    result=self.app.frame(dict(self.data,timestamp=now))
                if result['event_id']:
                    sent=result
        self.assertEqual(self.app.sender.intents, [])
        self.assertIsNotNone(sent)
        self.assertTrue(sent['release_camera'])
        self.assertEqual(sent['intent'], 'request_cup')
        self.app.execute()
        self.assertEqual(self.app.sender.intents, ['request_cup'])
