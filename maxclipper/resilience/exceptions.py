# Exception classes for MaxClipper resilience


class MaxClipperError(Exception):
    """Base exception for MaxClipper errors."""
    pass


class DownloadError(MaxClipperError):
    """Exception raised for download errors."""
    pass


class ProcessingError(MaxClipperError):
    """Exception raised for processing errors."""
    pass


class RenderError(MaxClipperError):
    """Exception raised for rendering errors."""
    pass


class ReframeError(MaxClipperError):
    """Exception raised for reframing errors."""
    pass


class CaptionError(MaxClipperError):
    """Exception raised for caption errors."""
    error_code: str = "MAXCLIPPER_ERROR"
    fix_action: str = "Check MaxClipper logs for details."

    def __init__(self, message: str, error_code: str | None = None,
                 fix_action: str | None = None):
        super().__init__(message)
        self.error_code = error_code or self.error_code
        self.fix_action = fix_action or self.fix_action


FONT_MISSING = "FONT_MISSING"