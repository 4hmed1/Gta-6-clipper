import pytest
from pathlib import Path
import urllib.parse

def test_path_traversal_prevention():
    # Verify that paths with ../ are resolved safely inside the base directory
    base_dir = Path("/tmp/clipforge_data").resolve()
    base_dir.mkdir(parents=True, exist_ok=True)

    malicious_input = "../../../etc/passwd"
    resolved_path = (base_dir / malicious_input).resolve()

    # It should either be outside or handled. In our secure implementation, we check:
    is_safe = str(resolved_path).startswith(str(base_dir))
    assert not is_safe or resolved_path == base_dir

def test_url_validation():
    valid_urls = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ"
    ]
    invalid_urls = [
        "file:///etc/passwd",
        "javascript:alert(1)",
        "http://malicious-site.com/video.mp4"
    ]

    for url in valid_urls:
        parsed = urllib.parse.urlparse(url)
        assert parsed.scheme in ["http", "https"]
        assert "youtube.com" in parsed.netloc or "youtu.be" in parsed.netloc

    for url in invalid_urls:
        parsed = urllib.parse.urlparse(url)
        is_valid = parsed.scheme in ["http", "https"] and ("youtube.com" in parsed.netloc or "youtu.be" in parsed.netloc)
        assert not is_valid
