# Exception classes for ClipForge resilience


class ClipForgeError(Exception):
    """Base exception for ClipForge errors."""
    pass


class DownloadError(ClipForgeError):
    """Exception raised for download errors."""
    pass


class ProcessingError(ClipForgeError):
    """Exception raised for processing errors."""
    pass


class RenderError(ClipForgeError):
    """Exception raised for rendering errors."""
    pass


class ReframeError(ClipForgeError):
    """Exception raised for reframing errors."""
    pass


class CaptionError(ClipForgeError):
    """Exception raised for caption errors."""
    pass