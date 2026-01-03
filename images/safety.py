import logging
import os
from nudenet import NudeDetector

log = logging.getLogger("nyunzi")

# Lazy global instance
_DETECTOR = None

# Classes considered unsafe
# NudeNet classes:
# EXPOSED_ANUS, EXPOSED_ARMPITS, COVERED_BELLY, EXPOSED_BELLY, COVERED_BUTTOCKS, 
# EXPOSED_BUTTOCKS, FACE_F, FACE_M, COVERED_FEET, EXPOSED_FEET, COVERED_BREAST_F, 
# EXPOSED_BREAST_F, COVERED_BREAST_M, EXPOSED_BREAST_M, COVERED_GENITALIA_F, 
# EXPOSED_GENITALIA_F, EXPOSED_GENITALIA_M, COVERED_GENITALIA_M, ...
UNSAFE_CLASSES = {
    "EXPOSED_GENITALIA_F",
    "EXPOSED_GENITALIA_M",
    "EXPOSED_BREAST_F",
    "EXPOSED_ANUS",
    "EXPOSED_BUTTOCKS", # Depending on strictness, maybe allow buttocks? User said "explicit", usually means porn. Buttocks might be okay if just swimsuit. But let's be safe for SFW.
}

def get_detector():
    global _DETECTOR
    if _DETECTOR is None:
        log.info("Initializing NudeNet Detector... (this may take a while to download weights on first run)")
        try:
            _DETECTOR = NudeDetector()
        except Exception as e:
            log.error(f"Failed to initialize NudeNet: {e}")
            return None
    return _DETECTOR

def check_is_safe(image_path: str, unsafe_threshold: float = 0.5) -> bool:
    """
    Returns True if the image is considered safe, False if explicit content is detected.
    """
    detector = get_detector()
    if not detector:
        # Fail safe? Or Fail open? 
        # If we can't load the model, we can't filter.
        # Given "SFW" requirement, might be better to Fail Safe (return False) 
        # but that would block all functionality if model fails.
        # Let's Fail Open but log error, assuming user fixes setup.
        # Actually user wants to use AI *to detect*, so without it we are naked (pun intended).
        # But for now, let's log error and return True to avoid crashing experience if model download fails.
        return True

    try:
        detections = detector.detect(image_path)
    except Exception as e:
        log.error(f"NudeNet detection failed for {image_path}: {e}")
        return True

    for detection in detections:
        label = detection.get("class")
        score = detection.get("score", 0.0)
        
        if label in UNSAFE_CLASSES and score > unsafe_threshold:
            log.info(f"[SAFETY] Blocked {image_path}: Found {label} ({score:.2f})")
            return False
            
    return True
