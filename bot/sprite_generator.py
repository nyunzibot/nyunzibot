import io
import math
from typing import Tuple
from PIL import Image, ImageSequence, ImageOps

def generate_vrc_sprite_sheet(gif_bytes: bytes, crop: bool = True) -> Tuple[bytes, int, int]:
    """
    Takes raw GIF bytes and generates a 1024x1024 sprite sheet PNG suitable for VRChat.
    Returns (png_bytes, frames_count, frames_over_time).
    """
    img = Image.open(io.BytesIO(gif_bytes))
    
    # Extract all frames
    frames = []
    for frame in ImageSequence.Iterator(img):
        # Convert to RGBA for transparency
        frames.append(frame.convert("RGBA"))
        
    num_frames = len(frames)
    
    # Cap at 64 frames (VRChat maximum)
    if num_frames > 64:
        # Subsample frames evenly
        step = num_frames / 64
        subsampled_frames = []
        for i in range(64):
            idx = min(int(i * step), num_frames - 1)
            subsampled_frames.append(frames[idx])
        frames = subsampled_frames
        num_frames = 64
        
    # Minimum 2 frames for animated
    if num_frames < 2:
        num_frames = 2
        if len(frames) == 1:
            frames.append(frames[0].copy())
        else:
            # Fallback if empty (shouldn't happen with valid image)
            frames = [Image.new("RGBA", (128, 128))] * 2

    # Calculate optimal grid size
    cols = math.ceil(math.sqrt(num_frames))
    rows = math.ceil(num_frames / cols)
    
    # Calculate cell size (VRC requires 1024x1024 sprite sheet)
    SHEET_SIZE = 1024
    cell_w = SHEET_SIZE // cols
    cell_h = SHEET_SIZE // rows
    
    # Create blank transparent canvas
    sprite_sheet = Image.new("RGBA", (SHEET_SIZE, SHEET_SIZE), (0, 0, 0, 0))
    
    for i, frame in enumerate(frames):
        if crop:
            # Resize and crop to fill the cell perfectly
            frame = ImageOps.fit(frame, (cell_w, cell_h), Image.Resampling.LANCZOS)
            x = (i % cols) * cell_w
            y = (i // cols) * cell_h
        else:
            # Resize frame to fit cell, maintaining aspect ratio (adds padding)
            frame.thumbnail((cell_w, cell_h), Image.Resampling.LANCZOS)
            x = (i % cols) * cell_w + (cell_w - frame.width) // 2
            y = (i // cols) * cell_h + (cell_h - frame.height) // 2
        
        sprite_sheet.paste(frame, (x, y), frame)
        
    # Export to bytes
    out_io = io.BytesIO()
    sprite_sheet.save(out_io, format="PNG")
    
    # FPS calculation (approximate from duration of first frame)
    duration_ms = img.info.get("duration", 100)
    if duration_ms == 0:
        duration_ms = 100
        
    fps = int(1000 / duration_ms)
    
    # VRChat allows 1-64 FPS
    fps = max(1, min(64, fps))
    
    return out_io.getvalue(), num_frames, fps
