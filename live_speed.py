"""Per-take live speed state shared with the native floating control."""

from contextlib import contextmanager
import fcntl
import json
from pathlib import Path

from project_store import atomic_write, write_json


@contextmanager
def control_lock(cache):
    with (cache / "hotkey.control.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def publish_take(cache, token, speed):
    path = cache / ("speed-" + token + ".txt")
    with control_lock(cache):
        atomic_write(path, str(speed))
        write_json(cache / "live-take.json", {"token": token, "initialSpeed": speed})
    return path


def finish_take(cache, token):
    with control_lock(cache):
        runtime = cache / "live-take.json"
        try:
            if json.loads(runtime.read_text()).get("token") == token:
                runtime.unlink()
        except (FileNotFoundError, ValueError):
            pass
        path = cache / ("speed-" + token + ".txt")
        try:
            path.unlink()
        except FileNotFoundError:
            pass
