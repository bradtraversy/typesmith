# TypeSmith control panel

The local macOS app prepares command and code steps for the global typing shortcut.
It stores recordings under `~/Library/Application Support/TypeSmith/` and runs
without a web server or package dependencies.

## Build and open

Run `python3 build_panel.py`, then open `build/TypeSmith.app`. Building requires
macOS and Xcode command line tools. The app bundles its Python backend and uses
macOS Python 3 and WebKit.

Configure the shortcut launcher to run `macos_hotkey.py --active --background`.
See [Keyboard shortcut setup](MACOS-HOTKEY.md) for permissions and cancellation.

## Select and type

Click a step to make it Active for hotkey. Each shortcut press repeats that step
until you select another. With unsaved edits, clicking a step only opens it in the
editor, and Save changes makes the selected step active. First step and Next step
explicitly change the active selection.

Edit the step name, type, source text, and speed, then Save changes. Command mode
leaves Return to you. Code mode sends the complete block, including line breaks.
For literal code entry, disable editor auto-indentation, automatic brackets and
quotes, format on type, and completion that changes Return or Tab behavior.

## Stop and resume

Choose After Escape or Stop, then Save changes:

- Restart from beginning: clear partial text before pressing the hotkey again.
- Resume where stopped: leave the cursor after the partial text, then press the
  hotkey to continue from the last confirmed character.

Completing a step resets its position. Saving or selecting a step clears a paused
position. TypeSmith does not restore your cursor or remove partial text. If a
helper failure makes the position uncertain, replay is blocked until you clear
partial text and reselect the step.

## Live speed

Show Live Speed opens a floating control. Hide for recording hides the main
window and leaves this control visible. Its slider is enabled during a take and
changes only that take's speed. Saved step speeds remain unchanged.

The floating window accepts focus. Typing pauses while TypeSmith is focused;
returning to the original editor resumes it. Switching to another app cancels
the take. Escape or Stop cancels using the recording's selected stop mode.

## App identity and menu bar

The T_ mark appears in the Dock/Finder app icon, control panel, floating speed
panel, and monochrome menu bar icon. The menu bar offers Open TypeSmith, Live
speed, and Quit. The build generates these assets from `panel/GenerateIcons.swift`.

## Implementation

The native app hosts a bundled offline interface. A restricted bridge sends
structured JSON to the backend. The backend owns project files and playback
state; the interface owns unsaved edits. Shared validation checks project files.
Atomic writes and revision checks protect saves. Control and active locks prevent
project mutation during a take.

Each take has a unique token, live speed file, and character checkpoint. The
worker checks cancellation between chunks and during waits. Cooperative shutdown
allows the last sent chunk to be recorded; forced or failed shutdown marks the
resume position uncertain. Timing uses monotonic elapsed time so scheduler delays
do not accumulate into long pauses.
