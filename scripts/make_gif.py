"""Stitch Playwright capture frames into the README hero GIF.

python scripts/make_gif.py docs/media/frames docs/media/demo.gif
"""

import sys
from itertools import pairwise
from pathlib import Path

from PIL import Image


def main(frames_dir: str, output: str, width: int = 1200) -> None:
    paths = sorted(Path(frames_dir).glob("*.png"), key=lambda p: int(p.stem))
    stamps = [int(p.stem) for p in paths]
    durations = [max(60, b - a) for a, b in pairwise(stamps)] + [2500]
    frames = []
    for path in paths:
        img = Image.open(path).convert("RGB")
        img = img.resize((width, round(img.height * width / img.width)), Image.Resampling.LANCZOS)
        quantized = img.quantize(128, Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
        frames.append(quantized)
    frames[0].save(
        output, save_all=True, append_images=frames[1:], duration=durations, loop=0, optimize=True
    )
    print(f"{output}: {len(frames)} frames, {Path(output).stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
