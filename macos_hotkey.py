"""Type successive script lines or a formatted code block into a macOS app."""

import argparse
import ctypes
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import uuid

from typesmith import typing_delay
from project_store import active_project_path, load_project, project_segments
from live_speed import publish_take, finish_take


APPLE_SCRIPT = r'''
use framework "Foundation"
use scripting additions

on readSpeed(speedPath, previousSpeed)
    set speedText to current application's NSString's stringWithContentsOfFile:speedPath encoding:(current application's NSUTF8StringEncoding) |error|:(missing value)
    if speedText is missing value then return previousSpeed
    set nextSpeed to (speedText's doubleValue()) as real
    if nextSpeed >= 1 and nextSpeed <= 500 then return nextSpeed
    return previousSpeed
end readSpeed

on shouldStop(cancelPath, token)
    set requestText to current application's NSString's stringWithContentsOfFile:cancelPath encoding:(current application's NSUTF8StringEncoding) |error|:(missing value)
    if requestText is missing value then return false
    return (requestText as text) is token
end shouldStop

on run argv
    set commandText to item 1 of argv
    set AppleScript's text item delimiters to ","
    set characterDelays to text items of (item 2 of argv)
    set AppleScript's text item delimiters to ""
    tell application "System Events"
        set targetProcess to first application process whose frontmost is true
        set targetID to unix id of targetProcess
        set targetBundle to bundle identifier of targetProcess
    end tell
    if targetBundle is "dev.typesmith.panel" then
        error "Hide TypeSmith and focus the terminal or editor before typing."
    end if
    if item 3 of argv is "block" and targetBundle is in {"com.github.wez.wezterm", "com.apple.Terminal", "com.googlecode.iterm2", "dev.warp.Warp-Stable", "co.zeit.hyper"} then
        error "Code blocks must be typed into an editor, not a terminal."
    end if
    set speedPath to item 4 of argv
    set currentSpeed to my readSpeed(speedPath, 40)
    set cursorPath to item 5 of argv
    set cancelPath to item 7 of argv
    set token to item 8 of argv
    set i to (item 6 of argv as integer) + 1
    repeat while i <= count characters of commandText
        if my shouldStop(cancelPath, token) then return "stopped"
        repeat
            if my shouldStop(cancelPath, token) then return "stopped"
            tell application "System Events"
                set focusedProcess to first application process whose frontmost is true
                set focusedBundle to bundle identifier of focusedProcess
            end tell
            if focusedBundle is not "dev.typesmith.panel" then exit repeat
            delay 0.05
        end repeat
        set currentSpeed to my readSpeed(speedPath, currentSpeed)
        set chunkSize to 1
        if currentSpeed > 50 then set chunkSize to (round (currentSpeed / 40) rounding down)
        set chunkEnd to i
        set nextCharacter to character i of commandText
        if nextCharacter is not linefeed and nextCharacter is not tab then
            repeat while chunkEnd < (count characters of commandText) and chunkEnd < i + chunkSize - 1
                set followingCharacter to character (chunkEnd + 1) of commandText
                if followingCharacter is linefeed or followingCharacter is tab then exit repeat
                set chunkEnd to chunkEnd + 1
            end repeat
        end if
        tell application "System Events"
            set currentProcess to first application process whose frontmost is true
            set currentID to unix id of currentProcess
            if currentID is not targetID then
                error "Typing stopped: target " & targetBundle & " (" & targetID & "), focused " & (bundle identifier of currentProcess) & " (" & currentID & ")."
            end if
            if nextCharacter is linefeed then
                key code 36
            else if nextCharacter is tab then
                key code 48
            else
                keystroke (text i thru chunkEnd of commandText)
            end if
        end tell
        set cursorText to current application's NSString's stringWithString:(chunkEnd as text)
        set checkpointSaved to cursorText's writeToFile:cursorPath atomically:true encoding:(current application's NSUTF8StringEncoding) |error|:(missing value)
        if not checkpointSaved then error "Could not save the typing position."
        set remainingUnits to 0
        repeat with delayIndex from i to chunkEnd
            if currentSpeed > 50 then
                set remainingUnits to remainingUnits + 1
            else
                set remainingUnits to remainingUnits + ((item delayIndex of characterDelays) as real)
            end if
        end repeat
        set previousTick to (current application's NSProcessInfo's processInfo()'s systemUptime()) as real
        repeat while remainingUnits > 0
            if my shouldStop(cancelPath, token) then return "stopped"
            set currentTick to (current application's NSProcessInfo's processInfo()'s systemUptime()) as real
            set remainingUnits to remainingUnits - ((currentTick - previousTick) * currentSpeed)
            set previousTick to currentTick
            if remainingUnits <= 0 then exit repeat
            set currentSpeed to my readSpeed(speedPath, currentSpeed)
            set sliceSeconds to remainingUnits / currentSpeed
            if sliceSeconds > 0.025 then set sliceSeconds to 0.025
            delay sliceSeconds
        end repeat
        set i to chunkEnd + 1
    end repeat
end run
'''


def read_commands(text, speed):
    commands = []
    for line in text.split("\n"):
        stripped = line.lstrip()
        if not stripped or stripped.startswith("# "):
            continue
        if stripped.startswith("#"):
            directive = stripped[1:].split(" #", 1)[0].split(None, 1)
            if len(directive) != 2 or directive[0].lower() != "speed":
                raise ValueError("Command sections support comments and #speed only.")
            speed = float(directive[1])
        else:
            if any(ord(char) < 32 or ord(char) == 127 for char in line):
                raise ValueError("Script lines cannot contain control characters.")
            if not math.isfinite(speed) or not 1 <= speed <= 500:
                raise ValueError("Typing speed must be between 1 and 500.")
            commands.append(("lines", line, speed))
    return commands, speed


def read_script(path, speed):
    if path.suffix.lower() == ".json":
        return project_segments(load_project(path))
    text = path.read_text()
    lines = text.splitlines(keepends=True)
    block_index = next((i for i, line in enumerate(lines)
                        if line.strip() == "#mode block"), None)
    prefix = text if block_index is None else "".join(lines[:block_index])
    segments, speed = read_commands(prefix, speed)
    if block_index is not None:
        body = "".join(lines[block_index + 1:])
        if body.startswith("#speed "):
            speed_line, _, body = body.partition("\n")
            speed = float(speed_line.split(None, 1)[1])
        if not body:
            raise ValueError("The code block is empty.")
        if not math.isfinite(speed) or not 1 <= speed <= 500:
            raise ValueError("Typing speed must be between 1 and 500.")
        if any((ord(char) < 32 and char not in "\n\t") or ord(char) == 127 for char in body):
            raise ValueError("Code blocks support tabs and newlines, but no other control characters.")
        segments.append(("block", body, speed))
    if not segments:
        raise ValueError("The shortcut script must contain some text.")
    return segments


def script_progress(cache, path, commands):
    key = hashlib.sha256(str(path.resolve()).encode()).hexdigest()
    state_path = cache / ("progress-" + key + ".json")
    fingerprint = hashlib.sha256(json.dumps(commands).encode()).hexdigest()
    index = 0
    try:
        saved = json.loads(state_path.read_text())
        if isinstance(saved, dict) and saved.get("fingerprint") == fingerprint:
            candidate = saved.get("next_line")
            if type(candidate) is int and 0 <= candidate < len(commands):
                index = candidate
    except (FileNotFoundError, ValueError):
        pass
    return state_path, fingerprint, index


def save_progress(path, fingerprint, index, offset=0, uncertain=False):
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as output:
        json.dump({"fingerprint": fingerprint, "next_line": index, "offset": offset, "uncertain": uncertain}, output)
    os.replace(output.name, path)


KARABINER_CLI = "/Library/Application Support/org.pqrs/Karabiner-Elements/bin/karabiner_cli"


class TypingCancelled(Exception):
    pass


class TypingUncertain(ValueError):
    pass


def set_hotkey_active(active):
    if Path(KARABINER_CLI).exists():
        subprocess.run(
            [KARABINER_CLI, "--set-variables", json.dumps({"typesmith_active": int(active)})],
            check=True,
        )


def request_stop(lock, cache):
    lock.seek(0)
    token = lock.read().strip()
    if not token:
        return
    with tempfile.NamedTemporaryFile(mode="w", dir=cache, delete=False) as request:
        request.write(token)
    os.replace(request.name, cache / "hotkey.cancel")


def check_cancelled(cache, token):
    try:
        if (cache / "hotkey.cancel").read_text() == token:
            raise TypingCancelled()
    except FileNotFoundError:
        pass


def wait_for_modifiers(cancel_check):
    core = ctypes.CDLL("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
    core.CGEventSourceFlagsState.argtypes = [ctypes.c_int]
    core.CGEventSourceFlagsState.restype = ctypes.c_uint64
    modifiers = (1 << 17) | (1 << 18) | (1 << 19) | (1 << 20)
    deadline = time.monotonic() + 5
    while core.CGEventSourceFlagsState(1) & modifiers:
        cancel_check()
        if time.monotonic() >= deadline:
            raise ValueError("Release the shortcut keys, then try again.")
        time.sleep(0.05)


def run_typing_process(argv, cancel_check):
    cancel_check()
    process = subprocess.Popen(argv)
    try:
        while process.poll() is None:
            try:
                cancel_check()
            except TypingCancelled:
                # Let the worker record its last sent chunk before stopping.
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    raise TypingUncertain("Typing did not stop cleanly. Clear partial text and reselect the step before replaying.")
                if process.returncode != 0:
                    raise TypingUncertain("Typing failed while stopping. Clear partial text and reselect the step before replaying.")
                raise
            time.sleep(0.02)
        if process.returncode:
            raise subprocess.CalledProcessError(process.returncode, argv)
        cancel_check()
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("script", type=Path, nargs="?")
    parser.add_argument("--speed", type=float, default=12)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--background", action="store_true")
    parser.add_argument("--stop", action="store_true")
    parser.add_argument("--active", action="store_true")
    args = parser.parse_args()
    if args.active and args.script is not None:
        parser.error("choose a script or --active, not both")
    if not args.stop and args.script is None and not args.active:
        parser.error("a script is required unless --stop is used")
    if args.dry_run:
        if args.stop:
            parser.error("--dry-run cannot be combined with --stop")
        script = active_project_path() if args.active else args.script.expanduser()
        segments = read_script(script, args.speed)
        print(json.dumps({"segments": [{"mode": mode, "text": text, "speed": speed, "press_enter": mode == "block" and "\n" in text} for mode, text, speed in segments]}))
        return
    if sys.platform != "darwin":
        raise ValueError("The global typing shortcut requires macOS.")
    if args.background and not args.stop:
        log = Path.home() / "Library/Logs/typesmith-hotkey.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a") as output:
            selection = ["--active"] if args.active else [str(args.script.expanduser().resolve())]
            subprocess.Popen(
                [sys.executable, str(Path(__file__).resolve())] + selection + ["--speed", str(args.speed)],
                stdin=subprocess.DEVNULL, stdout=output, stderr=output,
                start_new_session=True,
            )
        return
    cache = Path.home() / "Library/Caches/typesmith"
    cache.mkdir(parents=True, exist_ok=True)
    with (cache / "hotkey.lock").open("a+") as lock:
        # Serialize token publication and stop requests, then release this short
        # control lock while the active lock stays held throughout the take.
        with (cache / "hotkey.control.lock").open("a+") as control:
            fcntl.flock(control, fcntl.LOCK_EX)
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                request_stop(lock, cache)
                return
            if args.stop:
                set_hotkey_active(False)
                return
            script = active_project_path() if args.active else args.script.expanduser()
            token = uuid.uuid4().hex
            lock.seek(0)
            lock.truncate()
            lock.write(token)
            lock.flush()
        cancel_check = lambda: check_cancelled(cache, token)
        cursor_path = cache / ("cursor-" + token + ".txt")
        resume = False
        offset = 0
        state_path = None
        try:
            set_hotkey_active(True)
            cancel_check()
            commands = read_script(script, args.speed)
            state_path, fingerprint, index = script_progress(cache, script, commands)
            mode, command, speed = commands[index]
            resume = args.active and load_project(script).get("stopMode", "restart") == "resume"
            if resume and state_path.exists():
                saved = json.loads(state_path.read_text())
                if saved.get("fingerprint") == fingerprint and saved.get("uncertain"):
                    raise ValueError("Resume position is uncertain. Clear partial text and reselect the step before replaying.")
                candidate = saved.get("offset", 0)
                if saved.get("fingerprint") == fingerprint and saved.get("next_line") == index and type(candidate) is int and 0 <= candidate <= len(command.encode("utf-16-le")) // 2:
                    offset = candidate
            cursor_path.write_text(str(offset))
            wait_for_modifiers(cancel_check)
            speed_path = publish_take(cache, token, speed)
            # Relative timing weights preserve natural pauses as live speed changes.
            delays = ",".join(str(round(typing_delay(char, 12) * 12, 6)) for char in command)
            run_typing_process(
                ["/usr/bin/osascript", "-e", APPLE_SCRIPT, "--", command, delays, mode, str(speed_path), str(cursor_path), str(offset), str(cache / "hotkey.cancel"), token],
                cancel_check,
            )
            save_progress(state_path, fingerprint, index if args.active else (index + 1) % len(commands))
            if mode == "block":
                print("TypeSmith finished the code block.", flush=True)
            else:
                print("TypeSmith finished line {} of {}. Return was not pressed.".format(index + 1, len(commands)), flush=True)
        except TypingCancelled:
            if state_path is not None:
                position = int(cursor_path.read_text()) if resume and cursor_path.exists() else 0
                save_progress(state_path, fingerprint, index, position)
            print("TypeSmith paused." if resume else "TypeSmith stopped; next press restarts the step.", flush=True)
        except (subprocess.CalledProcessError, TypingUncertain):
            if resume and state_path is not None:
                save_progress(state_path, fingerprint, index, uncertain=True)
            raise
        finally:
            try:
                finish_take(cache, token)
                if cursor_path.exists():
                    cursor_path.unlink()
            finally:
                set_hotkey_active(False)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        print("TypeSmith: typing helper exited with status {}.".format(error.returncode), file=sys.stderr)
        sys.exit(1)
    except (ValueError, OSError) as error:
        print("TypeSmith: {}".format(error), file=sys.stderr)
        sys.exit(1)
