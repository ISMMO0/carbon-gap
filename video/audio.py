"""Build the film soundtrack: voiceover lines on cue + a quiet synth bed, ducked under the voice."""
import subprocess
from pathlib import Path

HERE = Path(__file__).parent
DUR = 30.6
# start time (s) of each voiceover line vo/s1..s9 (ElevenLabs, voice Sarah)
STARTS = [0.2, 2.45, 4.4, 10.1, 14.3, 18.7, 21.85, 23.9, 26.9]


def ff(*args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True, cwd=HERE)


inputs, chains = [], []
for i, t in enumerate(STARTS):
    inputs += ["-i", f"vo/s{i + 1}.wav"]
    ms = int(t * 1000)
    chains.append(f"[{i}:a]aresample=48000,adelay={ms}|{ms}[v{i}]")
mix = "".join(f"[v{i}]" for i in range(len(STARTS)))
ff(*inputs, "-filter_complex",
   ";".join(chains) + f";{mix}amix=inputs={len(STARTS)}:normalize=0,apad=whole_dur={DUR},atrim=0:{DUR},"
   "highpass=f=90,acompressor=threshold=-20dB:ratio=3:attack=5:release=80,loudnorm=I=-16:TP=-1.5[vo]",
   "-map", "[vo]", "-ac", "2", "-ar", "48000", "vo_track.wav")

pad = ("(0.16*sin(2*PI*110*t)+0.12*sin(2*PI*164.81*t)+0.10*sin(2*PI*220*t)+0.07*sin(2*PI*261.63*t)"
       "+0.05*sin(2*PI*329.63*t))*(0.75+0.25*sin(2*PI*0.25*t))"
       "+0.5*sin(2*PI*52*t)*exp(-9*mod(t,0.6))+0.035*sin(2*PI*1760*t)*exp(-40*mod(t+0.3,0.6))")
ff("-f", "lavfi", "-i", f"aevalsrc='{pad}':s=48000:d={DUR}",
   "-af", f"lowpass=f=1800,afade=t=in:d=1.2,afade=t=out:st={DUR - 2}:d=2,volume=-6dB", "-ac", "2", "bed.wav")

ff("-i", "bed.wav", "-i", "vo_track.wav", "-filter_complex",
   "[1:a]asplit[sc][v];[0:a][sc]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=300,volume=0.5[b];"
   "[b][v]amix=inputs=2:normalize=0,alimiter=limit=0.95[out]",
   "-map", "[out]", "mix.wav")
print("ok")
