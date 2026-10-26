"""Shared recording format and atomic local file operations."""

import hashlib
import json
import math
import os
from pathlib import Path
import tempfile


def support_dir():
    return Path.home() / "Library/Application Support/TypeSmith"


def active_project_path():
    settings = json.loads((support_dir() / "settings.json").read_text())
    if not isinstance(settings, dict) or not isinstance(settings.get("active_project"), str):
        raise ValueError("Open TypeSmith and choose a recording first.")
    return Path(settings["active_project"]).expanduser().resolve()


def atomic_write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as output:
            temporary = Path(output.name)
            output.write(content)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def write_json(path, value):
    atomic_write(path, json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def validate_project(value):
    if not isinstance(value, dict) or value.get("format") != "typesmith" or value.get("version") != 1:
        raise ValueError("Choose a TypeSmith recording file.")
    if value.get("stopMode", "restart") not in ("restart", "resume"):
        raise ValueError("Choose Restart or Resume after stopping.")
    name = value.get("name")
    steps = value.get("steps")
    if not isinstance(name, str) or not name.strip() or len(name) > 120:
        raise ValueError("Give this recording a name of 1 to 120 characters.")
    if not isinstance(steps, list) or not 1 <= len(steps) <= 100:
        raise ValueError("A recording needs between 1 and 100 steps.")
    ids = set()
    for number, step in enumerate(steps, 1):
        if not isinstance(step, dict):
            raise ValueError("Step {} is invalid.".format(number))
        identifier = step.get("id")
        title = step.get("title")
        mode = step.get("mode")
        text = step.get("text")
        speed = step.get("speed")
        if not isinstance(identifier, str) or not identifier or identifier in ids:
            raise ValueError("Each step needs a unique ID.")
        ids.add(identifier)
        if not isinstance(title, str) or not title.strip() or len(title) > 120:
            raise ValueError("Give step {} a short name.".format(number))
        if mode not in ("lines", "block"):
            raise ValueError("Choose Command or Code for step {}.".format(number))
        if not isinstance(text, str) or not text.strip() or len(text) > 10000:
            raise ValueError("Step {} needs text, up to 10,000 characters.".format(number))
        allowed = "\n\t" if mode == "block" else ""
        if any((ord(char) < 32 and char not in allowed) or ord(char) == 127 for char in text):
            raise ValueError("Step {} contains unsupported characters. Commands must be one line.".format(number))
        if type(speed) not in (int, float) or not math.isfinite(speed) or not 1 <= speed <= 500:
            raise ValueError("Step {} needs a speed from 1 to 500.".format(number))
    return value


def load_project(path):
    return validate_project(json.loads(Path(path).read_text()))


def project_segments(project):
    validate_project(project)
    return [(step["mode"], step["text"], step["speed"]) for step in project["steps"]]


def revision(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
