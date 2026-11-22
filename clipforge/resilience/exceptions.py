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
    error_code: str = "CLIPFORGE_ERROR"
    fix_action: str = "Check ClipForge logs for details."

    def __init__(self, message: str, error_code: str | None = None,
                 fix_action: str | None = None):
        super().__init__(message)
        self.error_code = error_code or self.error_code
        self.fix_action = fix_action or self.fix_action


FONT_MISSING = "FONT_MISSING"