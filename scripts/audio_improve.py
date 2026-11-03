"""FF voice preparation and adaptive, silence-aware speech editing.

Requires numpy, scipy, soundfile and ffmpeg. No external APIs or model weights.
The mild spectral suppressor is deliberately conservative: no hard noise gate.
Do not publish a personal recording or an unencrypted derived speaker sample.
"""
import argparse
import json
import math
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import ndimage, signal


def mono_wav(path, sample_rate=24000):
    cmd = ['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(path),
           '-vn','-ac','1','-ar',str(sample_rate),'-f','f32le','-acodec','pcm_f32le','-']
    output = subprocess.check_output(cmd)
    return np.frombuffer(output, dtype='<f4').copy(), sample_rate


def soft_denoise(data, sr, strength=0.55):
    """Use quieter frames to estimate stationary noise. Smooth gain > floor."""
    if not 0 <= strength <= 1:
        raise ValueError('strength must be between 0 and 1')
    arr = np.asarray(data, dtype=np.float64)
    if len(arr) < sr:
        raise ValueError('Voice reference should be longer than one second')
    arr = signal.sosfiltfilt(signal.butter(3, [75, 8500], btype='bandpass',
                                         fs=sr, output='sos'), arr)
    nfft, hop = 1024, 256
    f, t, spectrum = signal.stft(arr, fs=sr, nperseg=nfft,
                                  noverlap=nfft-hop, boundary='zeros')
    mag = abs(spectrum)
    # Quieter 12% frames excluding edges; minimum 6 frames avoids unstable noise estimate.
    frame_energy = np.sqrt(np.mean(mag**2,axis=0))
    cut = np.quantile(frame_energy, .12)
    quiet = frame_energy <= cut
    if quiet.sum() < 6:
        quiet[np.argsort(frame_energy)[:6]] = True
    noise = np.median(mag[:,quiet],axis=1)
    # Frequency-local, soft gains. Preserve faint consonants and room tone.
    floor = 0.35
    ratio = noise[:,None] / np.maximum(mag,1e-8)
    gain = 1.0 - strength * np.minimum(ratio**1.25, 1.25)
    gain = np.clip(gain,floor,1.0)
    gain = ndimage.gaussian_filter(gain,sigma=(1.1,1.8))
    # Extra soft reduction only in gaps, never a hard cutoff.
    body = ndimage.gaussian_filter1d((frame_energy > np.quantile(frame_energy,.28)).astype(float),sigma=2.0)
    gain *= (0.50 + 0.50 * body[None,:])
    _, out = signal.istft(spectrum*gain, fs=sr, nperseg=nfft,
                           noverlap=nfft-hop, input_onesided=True,boundary=True)
    out = out[:len(arr)]
    # No target loudness baked into speaker profile; conservative input headroom.
    rms = np.sqrt(np.mean(out**2) + 1e-14)
    target_rms=10**(-25/20)
    factor=min(target_rms/rms, 3.4, .88/(np.max(np.abs(out))+1e-12))
    return np.asarray(out*factor,dtype=np.float32)


def prepare_recording(source, output, *, strength=.55, sample_rate=24000):
    original,sr = mono_wav(source,sample_rate)
    cleaned = soft_denoise(original,sr,strength)
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    sf.write(output,cleaned,sr,subtype='PCM_16')
    metrics={
      'source_duration_s':round(len(original)/sr,3),
      'output_duration_s':round(len(cleaned)/sr,3),
      'sample_rate':sr,
      'strength':strength,
      'raw_rms_dbfs':round(float(20*np.log10(np.sqrt(np.mean(original**2))+1e-12)),2),
      'cleaned_rms_dbfs':round(float(20*np.log10(np.sqrt(np.mean(cleaned**2))+1e-12)),2),
      'peak_dbfs':round(float(20*np.log10(np.max(np.abs(cleaned))+1e-12)),2),
      'algorithm':'conservative bandpass + smoothed spectral suppression',
      'warning':'Speech reconstruction and room reverberation are not guaranteed.',
    }
    return metrics


def speech_bounds(y,sr,*,frame_ms=20,margin_ms=35):
    """Find a safe speech envelope; do not shorten internal phoneme pauses."""
    y=np.asarray(y,dtype=np.float32)
    if not len(y): raise ValueError('Empty speech segment')
    hop=max(1,int(sr*frame_ms/1000))
    length=int(np.ceil(len(y)/hop))
    padded=np.pad(y,(0,length*hop-len(y)))
    rms=np.sqrt(np.mean(padded.reshape(length,hop)**2,axis=1))
    noise=max(float(np.quantile(rms,.10)), 1e-5)
    peak=float(np.quantile(rms,.90))
    if peak < .0005:
        raise ValueError('Speech appears silent')
    threshold=max(noise*2.0,peak*.11,.00045)
    voiced=rms>threshold
    # Bridge micro-gaps, retaining consonants.
    voiced=ndimage.binary_closing(voiced,structure=np.ones(3),border_value=0)
    if not voiced.any(): raise ValueError('No speech detected')
    inds=np.where(voiced)[0]
    margin=round(margin_ms/frame_ms)
    a=max(0,(int(inds[0])-margin)*hop)
    b=min(len(y),(int(inds[-1])+1+margin)*hop)
    return a,b


def trim_segment(y,sr,*,fade_ms=12):
    a,b=speech_bounds(y,sr)
    clip=np.asarray(y[a:b],dtype=np.float32).copy()
    fade=min(round(sr*fade_ms/1000),len(clip)//4)
    if fade:
        clip[:fade]*=np.linspace(0,1,fade,dtype=np.float32)
        clip[-fade:]*=np.linspace(1,0,fade,dtype=np.float32)
    return clip


def compose_paced(segments, *, rate=48000, gap_s=.12, hook_gap_s=.07, ending_s=.20):
    """Compact each TTS scene, carry precise durations into renderer timeline.

    No time stretching. Gap is short and deterministic, breath space included.
    Input arrays must have already been resampled to `rate`.
    """
    if not segments:raise ValueError('No speech segments')
    chunks=[];durations=[]
    for i,x in enumerate(segments):
        clip=trim_segment(x,rate)
        if len(clip)<rate*.35:raise ValueError(f'Scene {i} too short after trimming')
        gap=ending_s if i==len(segments)-1 else (hook_gap_s if i==0 else gap_s)
        pad=np.zeros(round(gap*rate),dtype=np.float32)
        chunks.extend([clip,pad]);durations.append((len(clip)+len(pad))/rate)
    return np.concatenate(chunks), durations


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path)
    p.add_argument('output',type=Path)
    p.add_argument('--strength',type=float,default=.55)
    args=p.parse_args()
    print(json.dumps(prepare_recording(args.source,args.output,strength=args.strength),indent=2))

if __name__=='__main__':main()