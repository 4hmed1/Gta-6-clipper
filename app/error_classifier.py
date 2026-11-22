"""Error classification and recovery logic for ClipForge."""

from typing import Dict, Any, Optional

class ErrorClassifier:
    """Classifies errors into user-friendly messages and actionable fixes."""
    
    @staticmethod
    def classify(error: Any, stage: str = "unknown") -> Dict[str, str]:
        """Convert a raw exception or error message into a structured error object.
        
        Returns:
            Dict containing:
            - code: machine-readable code
            - title: plain-language short title
            - cause: one-sentence explanation of what happened
            - fix_action: what the user or system can do (retry, settings, etc.)
            - technical_detail: raw error for logs
        """
        err_str = str(error)
        err_lower = err_str.lower()
        
        # Default fallback
        result = {
            "code": "UNKNOWN_ERROR",
            "title": "Something went wrong",
            "cause": f"An unexpected error occurred during the {stage} stage.",
            "fix_action": "retry",
            "technical_detail": err_str
        }
        
        # Specific classifications
        if "sign in to confirm" in err_lower or "not a bot" in err_lower:
            result.update({
                "code": "YOUTUBE_BOT_DETECTION",
                "title": "YouTube Bot Detection",
                "cause": "YouTube blocked the request because it thinks you are a bot.",
                "fix_action": "use_cookies"
            })
        elif "private" in err_lower:
            result.update({
                "code": "PRIVATE_VIDEO",
                "title": "Private Video",
                "cause": "This video is private and cannot be downloaded.",
                "fix_action": "change_url"
            })
        elif "unavailable" in err_lower or "removed" in err_lower:
            result.update({
                "code": "VIDEO_UNAVAILABLE",
                "title": "Video Unavailable",
                "cause": "The video has been removed or is otherwise unavailable.",
                "fix_action": "change_url"
            })
        elif "geo" in err_lower or "blocked in your country" in err_lower:
            result.update({
                "code": "GEO_BLOCKED",
                "title": "Region Locked",
                "cause": "This video is not available in your region.",
                "fix_action": "use_vpn"
            })
        elif "403" in err_str:
            result.update({
                "code": "FORBIDDEN",
                "title": "Access Forbidden",
                "cause": "YouTube denied access (403 Forbidden).",
                "fix_action": "use_cookies"
            })
        elif "timeout" in err_lower or "timed out" in err_lower:
            result.update({
                "code": "NETWORK_TIMEOUT",
                "title": "Network Timeout",
                "cause": "The connection to YouTube timed out.",
                "fix_action": "retry"
            })
        elif "syntaxerror" in err_str or "invalid syntax" in err_lower:
            result.update({
                "code": "INTERNAL_SYNTAX_ERROR",
                "title": "Internal Error",
                "cause": "A code execution error occurred while processing the video.",
                "fix_action": "contact_support"
            })
        elif "captions_failed" in err_str or "caption" in err_lower:
            result.update({
                "code": "CAPTIONS_ERROR",
                "title": "Caption Error",
                "cause": "Could not generate accurate captions for this clip.",
                "fix_action": "retry_captions"
            })
        elif "no such file" in err_lower:
            result.update({
                "code": "FILE_NOT_FOUND",
                "title": "File Not Found",
                "cause": "A required file was missing during processing.",
                "fix_action": "retry"
            })
            
        return result
