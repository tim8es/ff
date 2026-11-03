"""Fan preset regression tests use entirely synthetic speech and appliance noise."""
import unittest
import numpy as np
from scripts.audio_fan import fan_reduce

class FanCleaningTests(unittest.TestCase):
    def setUp(self):
        self.sr=24000
        t=np.arange(self.sr*6)/self.sr
        self.speech=.055*np.sin(2*np.pi*215*t)+.012*np.sin(2*np.pi*432*t)
        self.speech[:self.sr]=0
        self.speech[-self.sr:]=0
        rng=np.random.default_rng(123)
        self.appliance=.012*np.sin(2*np.pi*894*t)+rng.normal(0,.003,len(t))
        self.noisy=self.speech+self.appliance

    def test_fan_preset_improves_background_to_voice_ratio(self):
        out=fan_reduce(self.noisy,self.sr,noise_audio=self.appliance[:self.sr],notch_hz=894)
        self.assertEqual(len(out),len(self.noisy))
        self.assertLess(np.max(abs(out)),.71)
        self.assertTrue(np.all(np.isfinite(out)))
        active=slice(self.sr*2,self.sr*4)
        def room_to_voice_ratio(y):
            return np.sqrt(np.mean(y[:self.sr]**2))/(np.sqrt(np.mean(y[active]**2))+1e-12)
        reduction=20*np.log10(room_to_voice_ratio(self.noisy)/room_to_voice_ratio(out))
        self.assertGreater(reduction,7)
        self.assertGreater(np.corrcoef(out[active],self.speech[active])[0,1],.92)

    def test_strong_preset_reduces_background_more_than_balanced(self):
        opts=dict(noise_audio=self.appliance[:self.sr],notch_hz=894)
        mild=fan_reduce(self.noisy,self.sr,**opts)
        strong=fan_reduce(self.noisy,self.sr,strong=True,**opts)
        active=slice(self.sr*2,self.sr*4)
        def ratio(y):return np.sqrt(np.mean(y[:self.sr]**2))/np.sqrt(np.mean(y[active]**2))
        self.assertLess(ratio(strong),ratio(mild)*.75)

    def test_notch_out_of_voice_band_and_short_noise_rejected(self):
        with self.assertRaisesRegex(ValueError,'Fan tone'):
            fan_reduce(self.noisy,self.sr,notch_hz=200)
        with self.assertRaisesRegex(ValueError,'Room tone'):
            fan_reduce(self.noisy,self.sr,noise_audio=np.zeros(10))

if __name__=='__main__':unittest.main()