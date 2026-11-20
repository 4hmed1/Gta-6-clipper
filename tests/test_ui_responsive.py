"""Playwright UI tests: the app bar must stay on ONE row at every width.

SPRINT Block C / checklist G: "header and cards look right at 360/768/1440 px".
The brand name, tabs and status chips are siblings in ``.app-bar-inner``;
if that row wraps, the header looks broken on a phone and a mid-size laptop.
"""

import os
import pytest

try:
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover - playwright is optional in some envs
    sync_playwright = None

pytestmark = pytest.mark.skipif(
    sync_playwright is None, reason="playwright not installed"
)

PORT = int(os.environ.get("CF_TEST_PORT", "8760"))
BASE_URL = f"http://127.0.0.1:{PORT}"


def _server_running() -> bool:
    import urllib.request
    try:
        with urllib.request.urlopen(f"{BASE_URL}/api/tasks", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


@pytest.fixture(scope="module")
def browser():
    if not _server_running():
        pytest.skip(f"server not running on {BASE_URL}")
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        yield b
        b.close()


@pytest.mark.parametrize("width", [360, 768, 1440])
def test_header_single_row(browser, width):
    page = browser.new_page(viewport={"width": width, "height": 900})
    page.goto(BASE_URL, wait_until="domcontentloaded")
    inner = page.query_selector(".app-bar-inner")
    assert inner is not None, "app-bar-inner missing"
    # The inner row must not wrap: its scrollHeight must equal its clientHeight
    # (no second line) and it must not scroll horizontally.
    info = inner.evaluate(
        """el => ({
        sh: el.scrollHeight,
        ch: el.clientHeight,
        sw: el.scrollWidth,
        cw: el.clientWidth,
        children: el.children.length,
    })"""
    )
    assert info["sh"] <= info["ch"] + 1, (
        f"app bar wrapped at {width}px: scrollHeight={info['sh']} > clientHeight={info['ch']}"
    )
    assert info["sw"] <= info["cw"] + 1, (
        f"app bar overflows horizontally at {width}px: "
        f"scrollWidth={info['sw']} > clientWidth={info['cw']}"
    )
    assert info["children"] >= 2, "app bar has no logo + nav + status"
    page.close()