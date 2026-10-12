"""
CUDAvidæo — Python GPU video generator (fixed).
CuPy genera frames en RTX 3050, libx264 encode a H.264.
Sin browser, sin CDP, sin CPU rendering.
"""
import cupy as cp
import numpy as np
from PIL import Image
import os
import subprocess
import time

# ── Config ──
WIDTH, HEIGHT = 720, 1280
FPS = 30
DURATION = 10
TOTAL_FRAMES = FPS * DURATION
OUTPUT_DIR = r"C:\æ\threejs-curriculo\cudavideo-frames"
OUTPUT_VIDEO = r"C:\æ\threejs-curriculo\cudavideo-python.mp4"
FFMPEG = r"C:\Users\yaelm\AppData\Local\hermes\tools\ffmpeg-7.1-nvenc\bin\ffmpeg.exe"

os.makedirs(OUTPUT_DIR, exist_ok=True)

print(f"CuPy: {cp.__version__}")
print(f"Device: {cp.cuda.runtime.getDeviceProperties(0)['name']}")
print(f"Generating {TOTAL_FRAMES} frames ({WIDTH}x{HEIGHT})...")

start = time.time()

# ── GPU Setup ──
N = 5000
positions = cp.random.randn(N, 3).astype(cp.float32)
velocities = cp.random.randn(N, 3).astype(cp.float32) * 0.03
colors = cp.random.rand(N, 3).astype(cp.float32)

void = cp.array([0.02, 0.02, 0.02], dtype=cp.float32)

# ── Generate frames ──
for frame_idx in range(TOTAL_FRAMES):
    t = frame_idx / FPS

    # Update positions on GPU
    positions += velocities
    positions = cp.where(positions > 6, 12 - positions, positions)
    positions = cp.where(positions < -6, -12 - positions, positions)

    # Project to 2D on GPU
    x = ((positions[:, 0] + 6) / 12 * WIDTH).astype(cp.int32)
    y = ((positions[:, 1] + 6) / 12 * HEIGHT).astype(cp.int32)

    # Create frame on GPU
    frame = cp.zeros((HEIGHT, WIDTH, 3), dtype=cp.float32)
    frame[:, :] = void

    # Valid particles
    valid = (x >= 0) & (x < WIDTH) & (y >= 0) & (y < HEIGHT)
    xv = x[valid]
    yv = y[valid]
    cv = colors[valid]

    # Draw particles using flat indexing (correct approach)
    flat_idx = yv * WIDTH + xv
    for c in range(3):
        channel = frame[:, :, c].ravel()
        cp.add.at(channel, flat_idx, cv[:, c])
        frame[:, :, c] = channel.reshape(HEIGHT, WIDTH)

    # Clamp
    frame = cp.minimum(frame, 1.0)

    # Transfer to CPU and save
    frame_cpu = (frame.get() * 255).astype(np.uint8)
    img = Image.fromarray(frame_cpu)
    img.save(os.path.join(OUTPUT_DIR, f"frame_{frame_idx:05d}.png"))

    if frame_idx % 30 == 0:
        elapsed = time.time() - start
        fps_actual = frame_idx / elapsed if elapsed > 0 else 0
        print(f"  Frame {frame_idx}/{TOTAL_FRAMES} ({elapsed:.1f}s, {fps_actual:.1f} fps)")

capture_time = time.time() - start
print(f"\nCapture done in {capture_time:.1f}s ({TOTAL_FRAMES/capture_time:.1f} fps)")

# ── Encode with libx264 (NVENC requires driver 610+, we have 592) ──
print(f"\nEncoding with libx264...")
encode_start = time.time()

cmd = [
    FFMPEG, "-y",
    "-framerate", str(FPS),
    "-i", os.path.join(OUTPUT_DIR, "frame_%05d.png"),
    "-c:v", "h264_nvenc",
    "-preset", "p7",
    "-cq", "20",
    "-pix_fmt", "yuv420p",
    "-movflags", "+faststart",
    OUTPUT_VIDEO
]
subprocess.run(cmd, check=True)

encode_time = time.time() - encode_start
print(f"Encode done in {encode_time:.1f}s")

size_mb = os.path.getsize(OUTPUT_VIDEO) / (1024 * 1024)
total_time = capture_time + encode_time
print(f"\n✅ CUDAvidæo Python demo created!")
print(f"   File: {OUTPUT_VIDEO}")
print(f"   Size: {size_mb:.1f} MB")
print(f"   Capture: {capture_time:.1f}s | Encode: {encode_time:.1f}s | Total: {total_time:.1f}s")
print(f"   Resolution: {WIDTH}x{HEIGHT} @ {FPS} FPS")
print(f"   Particles: {N}")
