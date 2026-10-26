# macOS typing shortcut

`macos_hotkey.py` types the next line from a script into the focused text field using
TypeSmith's natural character timing. It reads the file on every trigger, does
not open another window, and supports two modes.

## Commands: one line per press

Put one command or text segment on each line. Each shortcut press types the next
line without pressing Return. Blank lines and comments starting with `# ` are
skipped; `#speed` sets the speed for following lines. Control characters are
rejected so a script cannot submit text. After the last line, the next press
starts again at the first. Changing the text or speeds restarts the sequence.
A stopped or failed line is retried on the next press. Focus the text field where you want the text inserted. Typing
stops if the focused application changes. Triggering the shortcut again stops the
current take. The partial text stays in the field. Command mode never presses Return.

The shortcut works across apps, including terminals, editors, browser text fields,
and notes. Keep the intended field focused until typing finishes.

## Code: one complete block per press

Put `#mode block` before the code, optionally followed immediately by a
`#speed` line. Commands before that marker each get their own shortcut press.
The entire code block gets the next press. Everything after those headers is
literal code, including comments,
blank lines, leading spaces, tabs, and a final newline if present:

```text
#mode block
#speed 40
function hello() {
  console.log("Hello");
}
```

A block-only script replays the block on each press. A mixed script cycles
through its commands and then the full block, returning to the first command
afterward. Escape or a second shortcut press stops typing; clear partial code before replaying. This mode sends Return for newlines and
Tab for tabs. Use a code editor: several common terminal apps are rejected,
but other terminals can still receive Return. An integrated terminal or a
browser submit field cannot be distinguished from its editor or browser app.

The source whitespace is preserved, but editor typing assistance can change the
result. For literal code recordings in VS Code, disable auto indentation,
auto-closing brackets/quotes, format on type, suggestions on Enter, and tab
completion. Set `editor.insertSpaces` to `false` if the script contains literal
tabs. These settings are not changed automatically. Start at the intended column
in an empty area of the editor.

Speeds from 1 to 500 are supported. Above 50, short character bursts reduce
macOS event overhead. Actual speed still depends on the focused app.

## Shortcut setup

Inspect the script without sending keys:

```bash
python3 macos_hotkey.py /absolute/path/demo.txt --dry-run
```

For a global shortcut, use an existing keyboard shortcut utility to launch:

```bash
/usr/bin/python3 /absolute/path/typesmith/macos_hotkey.py /absolute/path/demo.txt --background
```

Karabiner-Elements can run this through a `shell_command` on `to_after_key_up`.
Account for Simple Modifications when choosing the modifier keys because those
are applied before Complex Modifications. Preserve existing rules when adding
the new shortcut. Leave out `frontmost_application_if` conditions to enable the
shortcut in every app.

For an emergency stop, bind Escape to the command below when Karabiner's
`typesmith_active` variable equals `1`. The helper sets that variable only while
a take is active, so Escape keeps its normal behavior at other times.

```bash
/usr/bin/python3 /absolute/path/typesmith/macos_hotkey.py --stop
```

Cancellation stops the current typing process without sending a key to the
app. A new take can be started after it stops. Clear the partial text
before starting again.

macOS may ask to let the shortcut host control System Events and use Accessibility
to send keystrokes. Those permissions must be granted by the user. Errors are
recorded in `~/Library/Logs/typesmith-hotkey.log`. Remove the shortcut rule to
disable it; there is no always-running TypeSmith service.
