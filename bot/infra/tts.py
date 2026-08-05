import os
import logging
from pathlib import Path
from gtts import gTTS

logger = logging.getLogger(__name__)

def generate_voice_note(text: str, output_path: Path, lang: str = 'hi') -> bool:
    """
    Generate a voice note from text using gTTS.
    lang='hi' for Hindi/Hinglish support.
    """
    try:
        # Hinglish works best with 'hi' (Hindi) or 'en' (English). 
        # Since the bot uses simple Hindi, 'hi' is a good default.
        tts = gTTS(text=text, lang=lang, slow=False)
        tts.save(str(output_path))
        return True
    except Exception as e:
        logger.error(f"TTS generation failed: {e}")
        return False
