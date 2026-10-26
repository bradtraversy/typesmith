"""Structured local actions for the TypeSmith desktop panel."""

from contextlib import contextmanager
import fcntl
import json
from pathlib import Path
import sys
import uuid

from macos_hotkey import read_script, request_stop, save_progress, script_progress
from project_store import (active_project_path, load_project, project_segments,
                           revision, support_dir, validate_project, write_json)


def cache_dir():
    path = Path.home() / "Library/Caches/typesmith"
    path.mkdir(parents=True, exist_ok=True)
    return path


@contextmanager
def editing_lock():
    cache = cache_dir()
    with (cache / "hotkey.control.lock").open("a+") as control, (cache / "hotkey.lock").open("a+") as active:
        try:
            fcntl.flock(control, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(active, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("Typing is active. Stop it before changing the recording.")
        yield


def is_typing():
    with (cache_dir() / "hotkey.lock").open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
    return False


def select_project(path):
    write_json(support_dir() / "settings.json", {"active_project": str(Path(path).resolve())})


def reset_progress(path, project, index=0):
    state_path, fingerprint, _ = script_progress(cache_dir(), path, project_segments(project))
    save_progress(state_path, fingerprint, index)


def initialize(import_path=None):
    settings = support_dir() / "settings.json"
    if settings.exists():
        return
    with editing_lock():
        if settings.exists():
            return
        if import_path:
            segments = read_script(Path(import_path), 40)
            steps = [{"id": uuid.uuid4().hex,
                      "title": "Code block {}".format(i) if mode == "block" else "Command {}".format(i),
                      "mode": mode, "text": text, "speed": speed}
                     for i, (mode, text, speed) in enumerate(segments, 1)]
            name = "Imported recording"
        else:
            name = "My recording"
            steps = [{"id": uuid.uuid4().hex, "title": "First command", "mode": "lines",
                      "text": 'echo "Ready to record"', "speed": 120}]
        project = validate_project({"format": "typesmith", "version": 1, "name": name, "steps": steps})
        path = support_dir() / "Projects" / (name + ".typesmith.json")
        if path.exists():
            path = path.with_name(name + "-" + uuid.uuid4().hex[:8] + ".typesmith.json")
        write_json(path, project)
        select_project(path)
        reset_progress(path, project)


def status():
    with (cache_dir() / "hotkey.control.lock").open("a+") as control:
        fcntl.flock(control, fcntl.LOCK_SH)
        return read_status()


def read_status():
    path = active_project_path()
    project = load_project(path)
    progress_path, fingerprint, next_index = script_progress(cache_dir(), path, project_segments(project))
    try:
        progress = json.loads(progress_path.read_text())
    except (FileNotFoundError, ValueError):
        progress = {}
    uncertain = isinstance(progress, dict) and progress.get("fingerprint") == fingerprint and bool(progress.get("uncertain"))
    return {"project": project, "path": str(path), "revision": revision(path),
            "nextIndex": next_index, "typing": is_typing(), "resumeUncertain": uncertain}


def handle(request):
    action = request.get("action")
    if action == "initialize":
        initialize(request.get("importPath"))
        return status()
    if action == "stop":
        cache = cache_dir()
        with (cache / "hotkey.control.lock").open("a+") as control, (cache / "hotkey.lock").open("a+") as active:
            fcntl.flock(control, fcntl.LOCK_EX)
            try:
                fcntl.flock(active, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                request_stop(active, cache)
        return {"stopping": True}
    if action == "state":
        initialize()
        return status()
    if action not in ("save", "open", "saveCopy", "reset", "skip", "setNext"):
        raise ValueError("Unknown panel action.")
    if action == "open":
        with editing_lock():
            destination = Path(request["destination"]).expanduser().resolve()
            project = load_project(destination)
            select_project(destination)
            reset_progress(destination, project)
        return status()
    with editing_lock():
        current_path = active_project_path()
        if request.get("path") != str(current_path):
            raise ValueError("The active recording changed. Reload before editing.")
        if action in ("save", "saveCopy"):
            project = validate_project(request.get("project"))
            if request.get("revision") != revision(current_path):
                raise ValueError("This recording changed elsewhere. Reload before saving.")
            destination = current_path if action == "save" else Path(request["destination"]).expanduser().resolve()
            if destination.suffix != ".json":
                raise ValueError("Save recordings with a .json extension.")
            selected_index = request.get("index", 0)
            if type(selected_index) is not int or not 0 <= selected_index < len(project["steps"]):
                raise ValueError("Choose an existing step.")
            write_json(destination, project)
            if action == "saveCopy":
                select_project(destination)
            reset_progress(destination, project, selected_index)
        else:
            if action == "setNext" and request.get("revision") != revision(current_path):
                raise ValueError("This recording changed elsewhere. Reload before selecting a step.")
            project = load_project(current_path)
            segments = project_segments(project)
            _, _, index = script_progress(cache_dir(), current_path, segments)
            if action == "reset":
                index = 0
            elif action == "skip":
                index = (index + 1) % len(segments)
            else:
                index = request.get("index")
                if type(index) is not int or not 0 <= index < len(segments):
                    raise ValueError("Choose an existing step.")
            reset_progress(current_path, project, index)
    return status()


if __name__ == "__main__":
    try:
        request = json.load(sys.stdin)
        if not isinstance(request, dict):
            raise ValueError("Invalid panel request.")
        result = {"ok": True, "data": handle(request)}
    except (OSError, ValueError, KeyError, TypeError) as error:
        result = {"ok": False, "error": str(error)}
    print(json.dumps(result))
