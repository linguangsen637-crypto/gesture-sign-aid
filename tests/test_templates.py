"""Regression checks for sequence rejection, held-out data and repeated events."""
import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest

HAS_NUMPY = importlib.util.find_spec('numpy') is not None
if HAS_NUMPY:
    from gesture_aid.perception.templates import TemplateBank, TriggerGate, dtw_distance, validate_frames


def clip(offset=0., reverse=False, count=24):
    frames=[]
    for i in range(count):
        phase=(count-1-i if reverse else i)/(count-1)
        frames.append(dict(t=i*3/(count-1), shape=[[offset+phase*.5]*63, [offset-phase*.3]*63],
                           wrists=[[phase*.4,-.4],[-.3,phase*.3]], valid=[True,True], body=True))
    return frames


@unittest.skipUnless(HAS_NUMPY, 'Install landmarks extra to test DTW')
class TemplateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.bank=TemplateBank(Path(self.temp.name))

    def ready(self):
        self.bank.save(clip(), 'cup','template','cup')
        self.bank.save(clip(2), 'negative','template','wave')

    def test_dtw_tolerates_speed_but_preserves_order_and_shape(self):
        self.assertLess(dtw_distance(clip(count=12),clip(count=40)), .03)
        self.assertGreater(dtw_distance(clip(),clip(reverse=True)), .1)
        self.assertGreater(dtw_distance(clip(),clip(2)), .5)

    def test_no_templates_or_no_negatives_cannot_accept(self):
        self.assertEqual(self.bank.match(clip())['reason'],'need_templates')
        self.bank.save(clip(),'cup','template')
        self.assertEqual(self.bank.match(clip())['gloss'],'unclear')

    def test_matching_positive_and_negative(self):
        self.ready()
        self.assertEqual(self.bank.match(clip(count=30))['gloss'],'cup')
        self.assertEqual(self.bank.match(clip(2))['gloss'],'unclear')
        self.assertEqual(self.bank.match(clip(5))['gloss'],'unclear')

    def test_ambiguous_identical_positive_and_negative_rejected(self):
        self.bank.save(clip(),'cup','template')
        self.bank.save(clip(),'negative','template')
        self.assertEqual(self.bank.match(clip())['gloss'],'unclear')

    def test_missing_hands_or_body_and_static_pose_rejected(self):
        self.ready()
        for key, value in [('valid',[False,False]),('body',False)]:
            frames=clip()
            for f in frames:f[key]=value
            self.assertEqual(self.bank.match(frames)['reason'],'quality')
        frames=clip()
        for f in frames:
            f['shape']=copy.deepcopy(frames[0]['shape'])
            f['wrists']=copy.deepcopy(frames[0]['wrists'])
        self.assertEqual(self.bank.match(frames)['reason'],'no_motion')

    def test_test_samples_never_participate_in_matching(self):
        self.bank.save(clip(),'cup','test')
        self.bank.save(clip(2),'negative','template')
        self.assertEqual(self.bank.match(clip())['reason'],'need_templates')
        reloaded=TemplateBank(Path(self.temp.name))
        self.assertEqual(reloaded.summary()['test_cup'],1)

    def test_invalid_features_and_timestamps_rejected(self):
        for change in (lambda f:f.update(t=float('nan')),lambda f:f.update(shape=[[0]*3]*2),lambda f:f.update(valid=[1,1])):
            frames=clip();change(frames[5])
            with self.assertRaises(ValueError):validate_frames(frames)
        frames=clip();frames[3]['t']=frames[2]['t']
        with self.assertRaises(ValueError):validate_frames(frames)

    def test_dedup_rearm_and_no_replay_while_holding(self):
        g=TriggerGate()
        self.assertIsNone(g.match(True,0))
        event=g.match(True,.5)
        self.assertIsNotNone(event)
        for t in [1,2,3,4]:self.assertIsNone(g.match(True,t))
        self.assertFalse(g.observe(True,4))
        self.assertFalse(g.observe(False,4.5))
        self.assertFalse(g.observe(True,5))
        self.assertTrue(g.observe(True,5.9))
        self.assertIsNone(g.match(True,6))
        self.assertNotEqual(g.match(True,6.5),event)

    def test_separated_hits_do_not_trigger(self):
        g=TriggerGate()
        self.assertIsNone(g.match(True,0))
        self.assertIsNone(g.match(True,2))
        self.assertIsNone(g.match(False,2.5))
        self.assertIsNone(g.match(True,3))
