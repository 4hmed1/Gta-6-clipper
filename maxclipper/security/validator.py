# Security Validator Module
# Validates URLs, file paths, and inputs to prevent security vulnerabilities

import re
from pathlib import Path
from urllib.parse import urlparse

SUPPORTED_HOSTS = {
    "youtube.com",
    "youtu.be",
    "youtube.com",  # Include subdomain variations
}

MAX_UPLOAD_SIZE = 500 * 1024 * 1024  # 500 MB

def validate_url(url: str) -> str:
    """
    Validate YouTube URLs for security.

    Args:
        url: The YouTube URL to validate

    Returns:
        The validated URL

    Raises:
        ValueError: If URL is invalid
    """
    if not isinstance(url, str):
        raise ValueError("URL must be a string")

    # Check URL scheme
    if not url.startswith(('http://', 'https://')):
        raise ValueError("URL must start with http:// or https://")

    try:
        parsed = urlparse(url)

        # Validate host
        if parsed.hostname not in SUPPORTED_HOSTS:
            raise ValueError(f"Unsupported host: {parsed.hostname}. Only YouTube URLs are allowed")

        # Validate path
        if not parsed.path or parsed.path == '/':
            raise ValueError("Invalid YouTube URL: missing video identifier")

        # Extract video ID for validation
        video_id = None
        if '/watch?v=' in parsed.path:
            video_id = parsed.query.split('=')[1].split('&')[0]
        elif '/shorts/' in parsed.path:
            video_id = parsed.path.split('/shorts/')[1].split('?')[0]
        elif '/live/' in parsed.path:
            video_id = parsed.path.split('/live/')[1].split('?')[0]

        if not video_id or len(video_id) < 5:
            raise ValueError("Invalid YouTube video ID")

    except Exception as e:
        raise ValueError(f"Invalid URL format: {str(e)}")

    return url

def sanitize_filename(filename: str) -> str:
    """
    Sanitize filenames to prevent path traversal attacks.

    Args:
        filename: The filename to sanitize

    Returns:
        Sanitized filename

    Raises:
        ValueError: If filename contains invalid characters
    """
    if not filename or not isinstance(filename, str):
        raise ValueError("Filename cannot be empty")

    # Remove path traversal sequences
    filename = filename.replace('..', '').replace('/', '').replace('\\', '')

    # Check for invalid characters
    invalid_chars = ['<', '>', ':', '"', '|', '?', '*']
    if any(char in filename for char in invalid_chars):
        raise ValueError(f"Filename contains invalid characters: {[c for c in invalid_chars if c in filename]}")

    # Limit filename length
    if len(filename) > 255:
        raise ValueError("Filename too long (max 255 characters)")

    # Ensure it's a valid filename
    if filename.strip() != filename or filename.startswith('.'):
        raise ValueError("Invalid filename format")

    return filename

def validate_file_size(file_size: int) -> bool:
    """
    Validate file size against maximum allowed size.

    Args:
        file_size: File size in bytes

    Returns:
        True if file size is valid

    Raises:
        ValueError: If file size exceeds limit
    """
    if file_size < 0:
        raise ValueError("File size cannot be negative")

    if file_size > MAX_UPLOAD_SIZE:
        raise ValueError(f"File too large. Maximum size is {MAX_UPLOAD_SIZE // (1024*1024)} MB")

    return True

def secure_join(base_dir: Path, subpath: str) -> Path:
    """
    Securely join base directory with subpath to prevent directory traversal.

    Args:
        base_dir: The base directory path
        subpath: The subpath to join

    Returns:
        The securely joined path

    Raises:
        ValueError: If path traversal is detected
    """
    # Resolve base directory
    base_dir = Path(base_dir).resolve()

    # Join and resolve
    target_path = (base_dir / subpath).resolve()

    # Check if target is still within base directory
    try:
        target_path.relative_to(base_dir)
    except ValueError:
        raise ValueError("Path traversal detected: attempted to access outside base directory")

    return target_path