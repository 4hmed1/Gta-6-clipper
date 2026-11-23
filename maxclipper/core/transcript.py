from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class TranscriptProvider(ABC):
    @abstractmethod
    def get_transcript(self, source: str) -> Dict[str, Any]:
        """
        Returns a dictionary with:
        {
            "success": bool,
            "text": str,
            "words": [
                {"word": str, "start": float, "end": float},
                ...
            ],
            "language": str,
            "error": Optional[str]
        }
        """
        pass

class YouTubeTranscriptProvider(TranscriptProvider):
    def get_transcript(self, source: str) -> Dict[str, Any]:
        # Implementation using yt-dlp to fetch json3 captions
        # This is the DEFAULT provider (deterministic)
        pass

class WhisperTranscriptProvider(TranscriptProvider):
    def __init__(self, model_size: str = "base"):
        self.model_size = model_size

    def get_transcript(self, source: str) -> Dict[str, Any]:
        # Implementation using faster-whisper (optional AI)
        pass

class LocalFileTranscriptProvider(TranscriptProvider):
    def get_transcript(self, source: str) -> Dict[str, Any]:
        # Implementation for local .srt / .vtt / .json files
        pass
