"""The dark palette is declared twice; these assert the two stay in sync.

One block serves "system" (a media query, no attribute set), the other serves
an explicit dark choice. If they drift, the page looks different depending on
how you arrived at dark, which is the kind of bug nobody reports and everyone
notices.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

CSS = Path(__file__).resolve().parents[1] / "web" / "src" / "styles.css"


@pytest.fixture(scope="module")
def css() -> str:
    return CSS.read_text()


def _tokens(block: str) -> dict[str, str]:
    return dict(re.findall(r"(--[a-z0-9-]+):\s*([^;]+);", block))


def _block(css: str, start_marker: str) -> str:
    start = css.index(start_marker)
    depth = 0
    for i in range(start, len(css)):
        if css[i] == "{":
            depth += 1
        elif css[i] == "}":
            depth -= 1
            if depth == 0:
                return css[start : i + 1]
    raise AssertionError(f"unbalanced braces after {start_marker!r}")


def test_the_two_dark_declarations_match(css):
    system_dark = _tokens(_block(css, "@media (prefers-color-scheme: dark)"))
    explicit_dark = _tokens(_block(css, ':root[data-theme="dark"]'))

    assert system_dark, "no tokens found in the system-dark block"
    assert system_dark == explicit_dark, (
        "the system-dark and explicit-dark palettes have drifted: "
        f"{set(system_dark.items()) ^ set(explicit_dark.items())}"
    )


def test_system_dark_is_guarded_against_an_explicit_light_choice(css):
    """Without the :not() guard, a dark OS overrides a deliberate light pick."""
    block = _block(css, "@media (prefers-color-scheme: dark)")
    assert ':root:not([data-theme="light"])' in block


def test_every_dark_token_is_defined_in_the_light_palette(css):
    """A token defined only in dark is undefined in light, and renders as nothing."""
    light = _tokens(_block(css, ":root {"))
    dark = _tokens(_block(css, ':root[data-theme="dark"]'))
    missing = set(dark) - set(light) - {"color-scheme"}
    assert not missing, f"defined only in dark: {sorted(missing)}"


def test_no_hardcoded_colours_outside_the_palettes(css):
    """A literal colour in a rule cannot respond to the theme."""
    palette_spans = [
        _block(css, ":root {"),
        _block(css, "@media (prefers-color-scheme: dark)"),
        _block(css, ':root[data-theme="dark"]'),
    ]
    body = css
    for span in palette_spans:
        body = body.replace(span, "")

    # #fff on a hover state of an accent-filled button is acceptable: the
    # button's background is an accent in both themes.
    offenders = [
        m
        for m in re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)", body)
        if m.lower() not in {"#fff", "#ffffff"}
    ]
    assert not offenders, f"hardcoded colours outside the palette: {sorted(set(offenders))}"
