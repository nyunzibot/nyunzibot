import io
import math
from typing import Tuple, Optional
from PIL import Image, ImageSequence, ImageOps

def generate_vrc_sprite_sheet(gif_bytes: bytes, crop: bool = True, grid_size: Optional[Tuple[int, int]] = None, background: str = 'transparent', target_fps: int = 0) -> Tuple[bytes, bytes, int, int]:
    """
    Takes raw GIF bytes and generates a 1024x1024 sprite sheet PNG suitable for VRChat.
    Returns (png_bytes, preview_gif_bytes, frames_count, frames_over_time).
    """
    img = Image.open(io.BytesIO(gif_bytes))
    
    # Extract all frames
    frames = []
    if getattr(img, "is_animated", False):
        try:
            import imageio.v3 as iio
            iio_frames = iio.imread(io.BytesIO(gif_bytes), index=None)
            # If imageio returns a single image (H, W, C), it failed to read as animated
            if len(iio_frames.shape) == 3 and iio_frames.shape[-1] in (3, 4):
                raise ValueError("imageio returned a single frame")
            for f in iio_frames:
                frames.append(Image.fromarray(f).convert("RGBA"))
        except Exception:
            for frame in ImageSequence.Iterator(img):
                frames.append(frame.convert("RGBA"))
    else:
        frames.append(img.convert("RGBA"))
        
    num_frames = len(frames)
    
    # Calculate optimal grid size or use provided
    if grid_size:
        cols, rows = grid_size
        max_frames = cols * rows
        if num_frames > max_frames:
            # Subsample frames evenly to fit grid
            step = num_frames / max_frames
            subsampled_frames = []
            for i in range(max_frames):
                idx = min(int(i * step), num_frames - 1)
                subsampled_frames.append(frames[idx])
            frames = subsampled_frames
            num_frames = max_frames
    else:
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
            
        # VRChat only supports specific square grid arrangements: 2x2, 4x4, and 8x8.
        # It maps the UVs based on these buckets.
        if num_frames <= 4:
            cols = rows = 2
        elif num_frames <= 16:
            cols = rows = 4
        else:
            cols = rows = 8
        
    # Minimum 2 frames for animated
    if num_frames < 2:
        num_frames = 2
        if len(frames) == 1:
            frames.append(frames[0].copy())
        else:
            # Fallback if empty (shouldn't happen with valid image)
            frames = [Image.new("RGBA", (128, 128))] * 2

    # Calculate cell size (VRC requires 1024x1024 sprite sheet)
    SHEET_SIZE = 1024
    cell_w = SHEET_SIZE // cols
    cell_h = SHEET_SIZE // rows
    
    # Create blank canvas based on background color
    if background == 'black':
        bg_color = (0, 0, 0, 255)
    elif background == 'white':
        bg_color = (255, 255, 255, 255)
    else:
        bg_color = (0, 0, 0, 0)
        
    sprite_sheet = Image.new("RGBA", (SHEET_SIZE, SHEET_SIZE), bg_color)
    
    processed_frames = []
    
    for i, frame in enumerate(frames):
        if crop:
            # Resize and crop to fill the cell perfectly
            frame = ImageOps.fit(frame, (cell_w, cell_h), Image.Resampling.LANCZOS)
            x = (i % cols) * cell_w
            y = (i // cols) * cell_h
            
            processed_frames.append(frame.copy())
            
            # If pasting onto a solid background, we need to use the frame as a mask
            if background in ('black', 'white'):
                sprite_sheet.paste(frame, (x, y), frame)
            else:
                sprite_sheet.paste(frame, (x, y))
        else:
            # Resize frame to fit cell, maintaining aspect ratio (adds padding)
            frame.thumbnail((cell_w, cell_h), Image.Resampling.LANCZOS)
            x = (i % cols) * cell_w + (cell_w - frame.width) // 2
            y = (i // cols) * cell_h + (cell_h - frame.height) // 2
            
            # Create a padded frame for the animated GIF preview so it matches the cell size
            pad_bg = bg_color if background in ('black', 'white') else (0, 0, 0, 0)
            padded_frame = Image.new("RGBA", (cell_w, cell_h), pad_bg)
            
            if background in ('black', 'white'):
                sprite_sheet.paste(frame, (x, y), frame)
                padded_frame.paste(frame, ((cell_w - frame.width) // 2, (cell_h - frame.height) // 2), frame)
            else:
                sprite_sheet.paste(frame, (x, y))
                padded_frame.paste(frame, ((cell_w - frame.width) // 2, (cell_h - frame.height) // 2))
                
            processed_frames.append(padded_frame)
        
    # Export to bytes
    out_io = io.BytesIO()
    sprite_sheet.save(out_io, format="PNG")
    
    # FPS calculation (approximate from duration of first frame)
    duration_ms = img.info.get("duration", 100)
    if duration_ms == 0:
        duration_ms = 100
        
    fps = int(1000 / duration_ms)
    
    if target_fps > 0:
        fps = target_fps
    
    # VRChat allows 1-64 FPS
    fps = max(1, min(64, fps))
    
    # Generate animated GIF preview
    preview_io = io.BytesIO()
    if len(processed_frames) > 0:
        # Calculate duration in ms for the GIF based on fps
        preview_duration = int(1000 / fps)
        processed_frames[0].save(
            preview_io, 
            format="GIF", 
            save_all=True, 
            append_images=processed_frames[1:], 
            duration=preview_duration, 
            loop=0,
            disposal=2,
            transparency=0
        )
    
    return out_io.getvalue(), preview_io.getvalue(), num_frames, fps
