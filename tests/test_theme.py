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

CSS = Path(__file__).resolve().parents[1] / "web" / "src" / "index.css"


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

    offenders = re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)", body)
    assert not offenders, f"hardcoded colours outside the palette: {sorted(set(offenders))}"


def test_components_never_name_a_colour_directly():
    """Tailwind classes must use semantic tokens, not palette literals.

    `bg-blue-500` cannot respond to the theme; `bg-multiverse` can, and also
    says what it means.
    """
    src = Path(__file__).resolve().parents[1] / "web" / "src"
    palette_classes = re.compile(
        r"\b(?:bg|text|border|ring|fill|stroke)-"
        r"(?:slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|"
        r"emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-\d{2,3}\b"
    )
    offenders: dict[str, set[str]] = {}
    for path in src.rglob("*.tsx"):
        found = set(palette_classes.findall(path.read_text()))
        if found:
            offenders[path.name] = found
    assert not offenders, f"literal palette classes found: {offenders}"
