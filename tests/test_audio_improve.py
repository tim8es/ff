"""Voice cleanup and shorts pacing regression tests; all signals are synthetic."""
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf

from scripts.audio_improve import (prepare_recording, speech_bounds,
                                   trim_segment, compose_paced)
from scripts.story_arc import validate_story_arc


class VoiceDSPTests(unittest.TestCase):
    def test_reference_cleanup_is_finite_and_timbre_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            sr=24000
            t=np.arange(sr*5)/sr
            rng=np.random.default_rng(15)
            # Unvoiced first/last 0.6s; speech voiced in between.
            envelope=np.where((t>=.6)&(t<=4.35), 1.0, 0.0)
            src=.035*np.sin(2*np.pi*210*t)*envelope
            noisy=src+.004*np.sin(2*np.pi*50*t)+rng.normal(0,.0015,len(t))
            fixture=root/"voice.wav";sf.write(fixture,noisy,sr)
            output=root/"clean.wav"
            receipt=prepare_recording(fixture,output)
            actual,sample_rate=sf.read(output)
            self.assertEqual(sr,sample_rate)
            self.assertEqual(len(actual),len(src))
            self.assertTrue(np.all(np.isfinite(actual)))
            self.assertLess(np.max(abs(actual)),.9)
            self.assertEqual(receipt["algorithm"],
                             "conservative bandpass + smoothed spectral suppression")
            # The voice frequency must remain; don't optimize for dead silence.
            inside=actual[int(sr*1):int(sr*4)]
            voice_correlation=np.corrcoef(
                inside,np.sin(2*np.pi*210*t[int(sr*1):int(sr*4)]))[0,1]
            self.assertGreater(voice_correlation,.85)

    def test_compact_timing_removes_padding_not_narration(self):
        sr=48000
        t=np.arange(int(sr*1.6))/sr
        tone=.07*np.sin(2*np.pi*280*t)
        raw=np.concatenate([np.zeros(int(sr*.8)),
                            tone.astype(np.float32),
                            np.zeros(int(sr*.9))])
        out,dur=compose_paced([raw,raw,raw],rate=sr,
                              gap_s=.12,hook_gap_s=.07,ending_s=.20)
        self.assertEqual(len(dur),3)
        self.assertLess(sum(dur),7.0) # fixed original clips total 9.9s
        self.assertGreater(sum(dur),4.3)
        self.assertAlmostEqual(len(out)/sr,sum(dur),places=4)
        self.assertAlmostEqual(dur[1]-dur[0],.05,delta=.04)
        self.assertTrue(np.max(abs(out))>.04)

    def test_silent_segment_rejected(self):
        with self.assertRaisesRegex(ValueError,"silent"):
            trim_segment(np.zeros(48000,dtype=np.float32),48000)


class ArcTests(unittest.TestCase):
    def good(self):
        return {"story_arc":{"hook":"Вы видели живое ископаемое?",
                             "evidence":"Существование древних линий",
                             "reveal":"Живое ископаемое тоже эволюционирует",
                             "payoff":"Вот почему прошлое живёт рядом с нами."},
                "scenes":[
                 {"beat":"hook","narration":"Вы видели живое ископаемое?","evidence":"https://a.example","visual_intent":"Question","motion_cue":"Silhouette reveal"},
                 {"beat":"evidence","narration":"...", "evidence":"https://b.example","visual_intent":"Fossil","motion_cue":"Timeline turns"},
                 {"beat":"evidence","narration":"...", "evidence":"https://a.example","visual_intent":"Time","motion_cue":"Era markers"},
                 {"beat":"reveal","narration":"...", "evidence":"https://b.example","visual_intent":"Change","motion_cue":"Morphology comparison"},
                 {"beat":"payoff","narration":"Вот почему прошлое живёт рядом с нами.", "evidence":"https://b.example","visual_intent":"Answer","motion_cue":"Reveal organism"},
                ]}
    def test_structure_checks_have_no_false_publication_approval(self):
        arc=validate_story_arc(self.good())
        self.assertTrue(arc["validated"])
        self.assertNotIn("release_ready",arc)
    def test_unspoken_hook_rejected(self):
        m=self.good()
        m["scenes"][0]["narration"]="Представьте себе..."
        with self.assertRaisesRegex(ValueError,"Hook must be audible"):
            validate_story_arc(m)
    def test_requires_payoff_and_evidence(self):
        m=self.good()
        m["scenes"][-1]["beat"]="evidence"
        with self.assertRaisesRegex(ValueError,"Final scene"):
            validate_story_arc(m)


if __name__=="__main__":
    unittest.main()
