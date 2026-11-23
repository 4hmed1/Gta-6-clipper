# Resilience Engine Module
# Handles checkpointed pipeline, fallback ladders, and self-healing capabilities

import hashlib
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional

from maxclipper.resilience.exceptions import (
    MaxClipperError,
    DownloadError,
    ProcessingError,
    RenderError,
    ReframeError,
    CaptionError,
)


class CheckpointManager:
    """Manages pipeline checkpointing and recovery."""

    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.checkpoint_dir = project_dir / "checkpoints"
        self.checkpoint_dir.mkdir(exist_ok=True)

    def save_checkpoint(self, stage_name: str, data: Dict[str, Any]) -> str:
        """Save stage data as a checkpoint.

        Args:
            stage_name: Name of the pipeline stage
            data: Data to checkpoint

        Returns:
            Checkpoint identifier
        """
        timestamp = int(time.time())
        checkpoint_id = f"{stage_name}_{timestamp}"

        # Create content hash for integrity verification
        content_hash = hashlib.sha256(json.dumps(data).encode()).hexdigest()

        checkpoint_file = self.checkpoint_dir / f"{checkpoint_id}_{content_hash[:8]}.json"

        checkpoint_data = {
            "stage_name": stage_name,
            "timestamp": timestamp,
            "content_hash": content_hash,
            "data": data,
        }

        with open(checkpoint_file, 'w') as f:
            json.dump(checkpoint_data, f, indent=2)

        return checkpoint_id

    def load_checkpoint(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """Load checkpoint data.

        Args:
            checkpoint_id: ID of checkpoint to load

        Returns:
            Checkpoint data or None if not found
        """
        for checkpoint_file in self.checkpoint_dir.glob(f"{checkpoint_id}_*.json"):
            try:
                with open(checkpoint_file) as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                continue
        return None

    def list_checkpoints(self, stage_name: str) -> list:
        """List checkpoints for a specific stage.

        Args:
            stage_name: Name of stage to list

        Returns:
            List of checkpoint IDs
        """
        return [f.stem.split('_')[0] for f in self.checkpoint_dir.glob(f"{stage_name}_*.json")]


class ErrorClassifier:
    """Classifies errors and provides automatic fix suggestions."""

    @staticmethod
    def classify_ffmpeg_error(error: str) -> tuple:
        """Classify FFmpeg errors.

        Args:
            error: FFmpeg error message

        Returns:
            Tuple of (error_type, fix_suggestion)
        """
        error_lower = error.lower()

        if "no such file or directory" in error_lower:
            return "MISSING_FILE", "Check if input file exists and path is correct"
        elif "permission denied" in error_lower:
            return "PERMISSION_DENIED", "Check file permissions and disk space"
        elif "codec not found" in error_lower:
            return "CODEC_NOT_FOUND", "Install required codec or try alternative encoder"
        elif "format not recognized" in error_lower:
            return "FORMAT_NOT_RECOGNIZED", "Check input file format or convert to supported format"
        elif "out of memory" in error_lower or "memory allocation" in error_lower:
            return "OUT_OF_MEMORY", "Reduce video resolution or use hardware acceleration"
        elif "decoder not found" in error_lower:
            return "DECODER_NOT_FOUND", "Install required decoder or use different input format"
        elif "encoder not found" in error_lower:
            return "ENCODER_NOT_FOUND", "Install required encoder or try different encoding parameters"
        else:
            return "UNKNOWN", "Try different encoding parameters or check FFmpeg documentation"

    @staticmethod
    def classify_ytdlp_error(error: str) -> tuple:
        """Classify yt-dlp errors.

        Args:
            error: yt-dlp error message

        Returns:
            Tuple of (error_type, fix_suggestion)
        """
        error_lower = error.lower()

        if "youtube" in error_lower and "error" in error_lower:
            return "YOUTUBE_API_ERROR", "Check YouTube API key or try different player client"
        elif "video unavailable" in error_lower:
            return "VIDEO_UNAVAILABLE", "Try a different video URL or check video privacy settings"
        elif "private" in error_lower:
            return "PRIVATE_VIDEO", "Need video owner consent or different access method"
        elif "network" in error_lower or "connection" in error_lower:
            return "NETWORK_ERROR", "Check internet connection and try again"
        elif "rate limit" in error_lower:
            return "RATE_LIMIT", "Wait and try again, or use a different player client"
        elif "format" in error_lower:
            return "FORMAT_ERROR", "Try different video format or quality setting"
        else:
            return "UNKNOWN", "Check network connection and try again with different settings"


class FallbackManager:
    """Manages fallback ladders for pipeline stages."""

    def __init__(self, checkpoint_manager: CheckpointManager):
        self.checkpoint_manager = checkpoint_manager

    def get_fallback_encoders(self, preferred_encoders: list) -> list:
        """Get list of encoder fallbacks.

        Args:
            preferred_encoders: Preferred encoders in order

        Returns:
            List of encoder fallbacks
        """
        # Hardware encoders in order of preference
        hardware_encoders = ["nvenc", "qsv", "videotoolbox", "vaapi", "amf"]
        software_encoder = "libx264"

        fallback_encoders = []

        # Add preferred encoders
        for encoder in preferred_encoders:
            if encoder in hardware_encoders:
                fallback_encoders.append(encoder)

        # Add software fallback if not already included
        if software_encoder not in fallback_encoders:
            fallback_encoders.append(software_encoder)

        return fallback_encoders

    def get_fallback_reframe_modes(self) -> list:
        """Get list of reframe mode fallbacks.

        Returns:
            List of reframe mode fallbacks
        """
        return ["smart_crop", "blur_fit", "center_crop", "keep_original"]

    def get_fallback_caption_modes(self) -> list:
        """Get list of caption mode fallbacks.

        Returns:
            List of caption mode fallbacks
        """
        return ["style_only", "basic", "simple", "text_only"]


class ResilienceEngine:
    """Main resilience engine for MaxClipper pipeline."""

    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.checkpoint_manager = CheckpointManager(project_dir)
        self.error_classifier = ErrorClassifier()
        self.fallback_manager = FallbackManager(self.checkpoint_manager)

    def process_with_resilience(self, stage_name: str, process_func, *args, **kwargs):
        """Process data with resilience and checkpointing.

        Args:
            stage_name: Name of pipeline stage
            process_func: Function to process
            *args: Arguments to pass to process_func
            **kwargs: Keyword arguments to pass to process_func

        Returns:
            Processed data

        Raises:
            MaxClipperError: If processing fails after all fallbacks
        """
        max_retries = 3
        fallback_attempts = 0

        for attempt in range(max_retries):
            try:
                # Process with current configuration
                result = process_func(*args, **kwargs)

                # Save checkpoint on success
                self.checkpoint_manager.save_checkpoint(stage_name, result)

                return result

            except Exception as e:
                # Classify error
                error_type = self._classify_error(e, stage_name)
                fix_suggestion = self._get_fix_suggestion(error_type, stage_name)

                if attempt < max_retries - 1:
                    # Try next fallback
                    fallback_attempts += 1
                    next_config = self._get_next_fallback(stage_name, fallback_attempts)

                    if next_config:
                        print(f"  [⚠️] Attempt {attempt + 1} failed: {str(e)}")
                        print(f"  [🔧] Trying fallback: {next_config}...")
                        result = process_func(*args, fallback_config=next_config, **kwargs)
                        self.checkpoint_manager.save_checkpoint(stage_name, result)
                        return result
                    else:
                        print(f"  [⚠️] Attempt {attempt + 1} failed: {str(e)}")
                        print(f"  [💡] Fix suggestion: {fix_suggestion}")
                else:
                    # All attempts failed
                    error_msg = f"Failed after {max_retries} attempts. Last error: {str(e)}"
                    error_msg += f"\nFix suggestion: {fix_suggestion}"
                    raise MaxClipperError(error_msg)

    def _classify_error(self, error: Exception, stage_name: str) -> str:
        """Classify error based on stage and error content.

        Args:
            error: The exception
            stage_name: Name of pipeline stage

        Returns:
            Error type
        """
        error_str = str(error)

        if stage_name == "download":
            return self.error_classifier.classify_ytdlp_error(error_str)[0]
        elif stage_name == "render":
            return self.error_classifier.classify_ffmpeg_error(error_str)[0]
        else:
            return "PROCESSING_ERROR"

    def _get_fix_suggestion(self, error_type: str, stage_name: str) -> str:
        """Get fix suggestion for error type.

        Args:
            error_type: Type of error
            stage_name: Name of pipeline stage

        Returns:
            Fix suggestion
        """
        if error_type == "MISSING_FILE":
            return "Check if input file exists and path is correct"
        elif error_type == "PERMISSION_DENIED":
            return "Check file permissions and disk space"
        elif error_type == "CODEC_NOT_FOUND":
            return "Install required codec or try alternative encoder"
        elif error_type == "OUT_OF_MEMORY":
            return "Reduce video resolution or use hardware acceleration"
        elif error_type == "YOUTUBE_API_ERROR":
            return "Check YouTube API key or try different player client"
        elif error_type == "VIDEO_UNAVAILABLE":
            return "Try a different video URL or check video privacy settings"
        else:
            return "Check logs for more details and try different settings"

    def _get_next_fallback(self, stage_name: str, attempt: int) -> Optional[Dict[str, Any]]:
        """Get next fallback configuration.

        Args:
            stage_name: Name of pipeline stage
            attempt: Number of failed attempts

        Returns:
            Next fallback configuration or None
        """
        if stage_name == "render":
            if attempt == 1:
                return {"encoder": "libx264", "preset": "ultrafast"}
            elif attempt == 2:
                return {"encoder": "libx264", "preset": "veryslow", "crf": 28}

        elif stage_name == "reframe":
            if attempt == 1:
                return {"mode": "blur_fit"}
            elif attempt == 2:
                return {"mode": "center_crop"}

        elif stage_name == "caption":
            if attempt == 1:
                return {"mode": "basic"}
            elif attempt == 2:
                return {"mode": "simple"}

        return None