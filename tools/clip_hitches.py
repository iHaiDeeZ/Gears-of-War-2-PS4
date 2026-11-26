#!/usr/bin/env python3
"""Hitches in a PS4 capture: runs of repeated frames (the game showed no new frame) and their lengths.

usage: clip_hitches.py <clip.mp4> <out.tsv> [<frames dir> <every N s>]
Per video frame: the mean absolute difference from the previous frame on a 160x90 grey thumbnail. A run of frames
with a difference under the threshold is a frame the game held on screen. Writes per-frame differences to out.tsv and
prints the capture rate, the runs longer than one game frame, and a histogram of how long each game frame stayed.
"""
import sys

import cv2
import numpy as np

path, out = sys.argv[1], sys.argv[2]
frames_dir = sys.argv[3] if len(sys.argv) > 3 else None
every = float(sys.argv[4]) if len(sys.argv) > 4 else 0

cap = cv2.VideoCapture(path)
fps = cap.get(cv2.CAP_PROP_FPS)
n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
print(f"{path}: {w}x{h}, {fps:.3f} fps, {n} frames, {n / fps:.1f} s", flush=True)

diffs = []
prev = None
k = 0
next_shot = 0.0
while True:
    ok, frame = cap.read()
    if not ok:
        break
    t = k / fps
    if frames_dir and every and t >= next_shot:
        cv2.imwrite(f"{frames_dir}/f_{t:07.2f}.jpg", cv2.resize(frame, (640, 360)), [cv2.IMWRITE_JPEG_QUALITY, 80])
        next_shot += every
    g = cv2.cvtColor(cv2.resize(frame, (160, 90), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY).astype(np.int16)
    d = float(np.mean(np.abs(g - prev))) if prev is not None else 99.0
    diffs.append(d)
    prev = g
    k += 1
cap.release()

with open(out, "w") as f:
    f.write("# frame\ttime_s\tdiff\n")
    for i, d in enumerate(diffs):
        f.write(f"{i}\t{i / fps:.3f}\t{d:.3f}\n")

TH = 0.35  # mean grey-level change under which two thumbnails are the same picture
# Runs of "same" frames: each run + the frame that started it = one game frame held on screen.
holds = []  # (start frame, frames held)
i = 0
while i < len(diffs):
    j = i + 1
    while j < len(diffs) and diffs[j] < TH:
        j += 1
    holds.append((i, j - i))
    i = j
hist = {}
for s, c in holds:
    hist[c] = hist.get(c, 0) + 1
print("frames each picture stayed on screen (count of pictures):")
for c in sorted(hist):
    if c <= 12:
        print(f"  {c} ({c / fps * 1000:.0f} ms): {hist[c]}")
long = sum(v for c, v in hist.items() if c > 12)
print(f"  more than 12: {long}")
# Hitches: a picture held 3+ capture frames while the pictures around it changed every 1-2 (moving scene).
print("long holds (>= 3 frames at a 30 fps capture, i.e. >= 100 ms) in moving stretches:")
shown = 0
for idx, (s, c) in enumerate(holds):
    if c * (30.0 / fps) < 3:
        continue
    before = [cc for _, cc in holds[max(0, idx - 6):idx]]
    after = [cc for _, cc in holds[idx + 1:idx + 7]]
    moving = before and after and max(before) <= 2 and max(after) <= 2
    if moving or c * (30.0 / fps) >= 6:
        print(f"  t={s / fps:7.2f} s: held {c} frames ({c / fps * 1000:.0f} ms){'' if moving else ' (static around)'}")
        shown += 1
print(f"{shown} listed")
