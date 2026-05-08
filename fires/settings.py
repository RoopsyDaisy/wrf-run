"""Per-user/per-environment settings loader and {{ placeholder }} renderer."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

PLACEHOLDER_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")
DEFAULT_PATH = Path(__file__).resolve().parent.parent / "configs" / "settings.yaml"
REQUIRED_KEYS = ("user", "project")


def load_settings(path: Path | None = None) -> dict[str, str]:
    target = path or DEFAULT_PATH
    if not target.exists():
        example = target.parent / f"{target.name}.example"
        raise SystemExit(
            f"Settings file not found: {target}\n"
            f"Copy {example} to {target} and fill in your values."
        )
    with target.open() as fh:
        data = yaml.safe_load(fh) or {}
    for key in REQUIRED_KEYS:
        if key not in data:
            raise SystemExit(f"{target}: missing required key '{key}'")
        if data[key] == "CHANGE_ME":
            raise SystemExit(f"{target}: replace CHANGE_ME for key '{key}'")
    data.setdefault("home_root", f"/glade/u/home/{data['user']}")
    data.setdefault("scratch_root", f"/glade/derecho/scratch/{data['user']}")
    data.setdefault("workflow_root", f"{data['scratch_root']}/workflow")
    data.setdefault("grib_root", f"{data['scratch_root']}/data/hrrr")
    return data


def render(text: str, settings: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in settings:
            known = ", ".join(sorted(settings))
            raise KeyError(f"Unknown placeholder {{{{ {key} }}}}; known: {known}")
        return str(settings[key])

    return PLACEHOLDER_RE.sub(replace, text)
