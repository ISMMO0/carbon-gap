"""Mix the demo soundtrack from audio_events.json and encode the MP4.

Run after record_demo.py: backend/.venv/bin/python video/demo/build_demo.py
"""
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).parent
FPS = 30


def ff(*args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True, cwd=HERE)


def main():
    events = json.loads((HERE / "audio_events.json").read_text())
    frames = len(list((HERE / "frames").glob("*.jpg")))
    dur = frames / FPS
    inputs, chains = [], []
    for i, (t, path) in enumerate(events):
        inputs += ["-i", path]
        ms = int(t * 1000)
        chains.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=mono,adelay={ms}[v{i}]")
    mix = "".join(f"[v{i}]" for i in range(len(events)))
    ff(*inputs, "-filter_complex", ";".join(chains) + f";{mix}amix=inputs={len(events)}:normalize=0,apad=whole_dur={dur},"
       f"atrim=0:{dur},highpass=f=80,acompressor=threshold=-20dB:ratio=3:attack=5:release=80,loudnorm=I=-16:TP=-1.5[vo]",
       "-map", "[vo]", "-ac", "2", "-ar", "48000", "demo_vo.wav")
    pad = ("(0.14*sin(2*PI*110*t)+0.10*sin(2*PI*164.81*t)+0.08*sin(2*PI*220*t)+0.05*sin(2*PI*329.63*t))"
           "*(0.75+0.25*sin(2*PI*0.2*t))+0.03*sin(2*PI*1760*t)*exp(-40*mod(t+0.3,0.75))")
    ff("-f", "lavfi", "-i", f"aevalsrc='{pad}':s=48000:d={dur}", "-af",
       f"lowpass=f=1600,afade=t=in:d=1.5,afade=t=out:st={dur - 3}:d=3,volume=-9dB", "-ac", "2", "demo_bed.wav")
    ff("-i", "demo_bed.wav", "-i", "demo_vo.wav", "-filter_complex",
       "[1:a]asplit[sc][v];[0:a][sc]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=400,volume=0.6[b];"
       "[b][v]amix=inputs=2:normalize=0,alimiter=limit=0.95[out]", "-map", "[out]", "demo_mix.wav")
    ff("-framerate", str(FPS), "-i", "frames/%05d.jpg", "-i", "demo_mix.wav", "-c:v", "libx264", "-preset", "slow",
       "-crf", "18", "-pix_fmt", "yuv420p", "-vf", "scale=1920:1080:flags=lanczos", "-movflags", "+faststart",
       "-c:a", "aac", "-b:a", "192k", "-shortest", "carbon-gap-demo.mp4")
    print(f"carbon-gap-demo.mp4: {dur:.1f}s")


if __name__ == "__main__":
    main()
