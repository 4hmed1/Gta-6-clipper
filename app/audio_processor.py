import subprocess
from pathlib import Path
from typing import Optional

def process_audio_for_broadcast(
    input_video: str,
    bg_music: Optional[str] = None,
    output_video: str = "output_broadcast.mp4"
):
    """
    1. Trims silence (>0.4s)
    2. Broadcast vocal clarity (HPF, Compressor, Loudnorm)
    3. Music ducking via sidechain compression
    """

    # Base chain for vocal processing
    # silenceremove: start_periods=1:start_duration=0.4:start_threshold=-30dB
    # loudnorm: standard broadcast spec
    vocal_chain = (
        "silenceremove=start_periods=1:start_duration=0.4:start_threshold=-30dB,"
        "highpass=f=80,"
        "acompressor=threshold=-20dB:ratio=4,"
        "loudnorm=I=-14:TP=-1.5:LRA=11"
    )

    cmd = ["ffmpeg", "-y", "-i", input_video]

    if bg_music:
        cmd += ["-i", bg_music]
        # Ducking: sidechain compressor on music stream [1:a] using vocal [0:a] as sidechain
        # Music ducked by 15dB when voice detected
        filter_complex = (
            f"[0:a]{vocal_chain}[vocal];"
            f"[1:a]sidechaincompress=threshold=0.01:ratio=5:level=1:sidechain=[vocal][music];"
            f"[vocal][music]amix=inputs=2:duration=first"
        )
        cmd += ["-filter_complex", filter_complex]
    else:
        cmd += ["-af", vocal_chain]

    cmd += [
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        output_video
    ]

    subprocess.run(cmd, check=True, timeout=30)
    return output_video
