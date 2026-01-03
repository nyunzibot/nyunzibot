import logging
import os

log = logging.getLogger("nyunzi")

# Lazy global instance
_MODEL = None
_MODEL_PATH = None

# Categories from nsfw-detector:
# - 'drawings': Safe for work drawings, including anime
# - 'hentai': Hentai and pornographic drawings
# - 'neutral': Safe content
# - 'porn': Pornographic photos
# - 'sexy': Sexy/suggestive content

# Thresholds for classification
UNSAFE_THRESHOLD = 0.3  # If any unsafe category exceeds this, block
UNSAFE_CATEGORIES = {'hentai', 'porn', 'sexy'}


def get_model():
    """
    Lazy-load the nsfw-detector model.
    Downloads model on first use (~89MB).
    """
    global _MODEL, _MODEL_PATH
    
    if _MODEL is not None:
        return _MODEL
    
    log.info("Initializing NSFW Detector... (this may take a while on first run)")
    
    try:
        from nsfw_detector import predict
        
        # Check if we have a local model path, otherwise use default
        # The model will be downloaded automatically if not present
        _MODEL = predict.load_model('./nsfw_mobilenet2.224x224.h5')
        log.info("NSFW Detector initialized successfully")
        return _MODEL
        
    except FileNotFoundError:
        # Try downloading model
        log.info("Model not found locally, attempting to use default model...")
        try:
            from nsfw_detector import predict
            # Use the default mobilenet model
            import nsfw_detector
            model_dir = os.path.dirname(nsfw_detector.__file__)
            default_model = os.path.join(model_dir, 'nsfw_mobilenet2.224x224.h5')
            
            if os.path.exists(default_model):
                _MODEL = predict.load_model(default_model)
                log.info("NSFW Detector initialized with default model")
                return _MODEL
            else:
                log.error("NSFW model not found. Download from: https://github.com/GantMan/nsfw_model")
                return None
        except Exception as e:
            log.error(f"Failed to initialize NSFW Detector: {e}")
            return None
            
    except Exception as e:
        log.error(f"Failed to initialize NSFW Detector: {e}")
        return None


def check_is_safe(image_path: str, unsafe_threshold: float = UNSAFE_THRESHOLD) -> bool:
    """
    Returns True if the image is considered safe (drawings/neutral),
    False if explicit content is detected (hentai/porn/sexy).
    
    Uses nsfw-detector which is specifically trained on anime content.
    """
    from config import ENABLE_NSFW_DETECTOR
    if not ENABLE_NSFW_DETECTOR:
        return True

    model = get_model()
    if not model:
        # Fail open if model not available
        log.warning("[SAFETY] Model not available, allowing image through")
        return True

    try:
        from nsfw_detector import predict
        
        # Classify the image
        result = predict.classify(model, image_path)
        
        if not result or image_path not in result:
            log.warning(f"[SAFETY] No classification result for {image_path}")
            return True
        
        scores = result[image_path]
        
        # Check unsafe categories
        for category in UNSAFE_CATEGORIES:
            score = scores.get(category, 0.0)
            if score > unsafe_threshold:
                log.info(f"[SAFETY] Blocked {image_path}: {category}={score:.2f}")
                return False
        
        # Log what we detected
        drawings_score = scores.get('drawings', 0.0)
        neutral_score = scores.get('neutral', 0.0)
        hentai_score = scores.get('hentai', 0.0)
        
        log.debug(f"[SAFETY] Allowed {image_path}: drawings={drawings_score:.2f}, neutral={neutral_score:.2f}, hentai={hentai_score:.2f}")
        return True
            
    except Exception as e:
        log.error(f"NSFW detection failed for {image_path}: {e}")
        return True
