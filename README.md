# Typesmith

A terminal auto-typer for recording tutorials, demos, and videos. Typesmith simulates natural human typing in your terminal — character by character with realistic variable speed — so your recordings look like someone is actually typing, not pasting.

Commands are executed by default, so you get real output just like a live terminal session.

## Features

- **Natural typing simulation** with gaussian-distributed keystroke delays, word-boundary pauses, punctuation hesitation, and occasional "thinking" pauses
- **Script mode** for pre-planned recordings — load a script file and step through commands with a keypress
- **Interactive mode** for ad-hoc demos — paste or type commands and they get replayed with the typing effect
- **Real command execution** by default — commands actually run and show real output
- **Speed control** — adjust globally via CLI flags or per-command via script directives
- **Zero dependencies** — Python 3 standard library only

## Requirements

- Python 3.6+ (`python3`)
- Linux or macOS (uses POSIX terminal controls)

## Installation

```bash
# Install from PyPI
pip install typesmith

# Or install with pipx (recommended for CLI tools)
pipx install typesmith
```

## Quick Start

```bash
# Interactive mode — type commands, watch them get re-typed
typesmith

# Script mode — step through pre-written commands
typesmith run example.txt
```

## Usage

### Interactive Mode

```bash
typesmith [options]
```

Launches an interactive session. The screen clears, and you'll see a dim `(input)` prompt. Type or paste a command and press Enter. Typesmith erases your raw input and re-types it character by character with the typing effect, then executes it.

**Example session:**

```
(input) echo "Hello, World!"     <-- you type this (gets erased)
$ echo "Hello, World!"           <-- typesmith re-types this slowly
Hello, World!                    <-- real command output
(input) ls                       <-- next command
$ ls                             <-- re-typed
README.md  typesmith.py  example.txt
```

You can also enter directives inline during interactive mode:

```
(input) #speed 20        <-- changes speed on the fly
(input) #clear           <-- clears the screen
(input) #prompt >>>      <-- changes the displayed prompt
```

Press `Ctrl+C` to exit.

### Script Mode

```bash
typesmith run <script-file> [options]
```

Loads commands from a script file and plays them back one at a time. The screen clears, and Typesmith waits for you to press **Enter** or **Space** to trigger each command. This is ideal for recording because the keypresses are invisible in the output.

**Example workflow for recording:**

1. Write your commands in a script file
2. Start your screen recorder (OBS, asciinema, etc.)
3. Run `typesmith run demo.txt`
4. Press Enter to trigger each command — it types naturally and runs
5. Stop recording

Press `q` or `Ctrl+C` to exit early.

## CLI Options

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--speed` | `-s` | `12` | Base typing speed in characters per second |
| `--variance` | `-v` | `0.4` | Speed variance from 0.0 (uniform) to 1.0 (erratic) |
| `--prompt` | `-p` | `"$ "` | Shell prompt string displayed before each command |
| `--execute` | `-x` | off | Execute commands after typing them |

**Examples:**

```bash
# Slow, deliberate typing
typesmith -s 6

# Fast typing with lots of variation
typesmith -s 20 -v 0.8

# Custom prompt that looks like zsh
typesmith -p "% "

# Execute commands after typing them
typesmith -x

# Combine options with script mode
typesmith run demo.txt -s 15 -p ">>> "
```

## Script File Format

Script files are plain text with one command per line. Lines starting with `#` are either comments or directives.

```bash
# This is a comment (ignored)

echo "First command"

#speed 15          # set typing speed to 15 chars/sec
ls -la

#pause 1.5         # wait 1.5 seconds before the next command
#speed 8           # slow down
cat README.md

#clear             # clear the screen
#prompt >>>        # change the prompt
python3 --version

#speed 12          # back to normal
echo "Done!"
```

### Directives Reference

| Directive | Description | Example |
|-----------|-------------|---------|
| `#speed <n>` | Set typing speed to `n` characters/sec | `#speed 15` |
| `#pause <n>` | Pause for `n` seconds before the next command | `#pause 2.0` |
| `#prompt <str>` | Change the displayed shell prompt | `#prompt >>>` |
| `#clear` | Clear the terminal screen | `#clear` |

Directives apply to the command that follows them. You can stack multiple directives before a single command. Inline comments on directive lines are supported (e.g., `#speed 15  # faster for simple commands`).

### Comments

Lines starting with `# ` (hash followed by a space) are treated as comments and ignored entirely. This distinguishes them from directives which start with `#` immediately followed by the directive name.

```bash
# This is a comment
#speed 12          <-- this is a directive
```

## How the Typing Simulation Works

Typesmith doesn't just add a fixed delay between characters. It simulates realistic human typing patterns:

1. **Base delay** — calculated from your speed setting (`1 / speed` seconds per character)
2. **Gaussian jitter** — each keystroke varies randomly around the base delay, controlled by the variance setting
3. **Word boundary pauses** — small extra delay after spaces, simulating the natural pause between words
4. **Punctuation hesitation** — slightly longer pauses after `. , ; : ! ?` since these keys are typically hit more deliberately
5. **Thinking pauses** — roughly 2% of keystrokes get a longer random pause (0.2-0.5s), simulating moments of thought

The result looks convincingly human, especially at moderate speeds (8-15 cps).

## Tips for Recording

- **Speed 8-12** looks most natural for tutorials where viewers need to follow along
- **Speed 15-20** is good for sections where you're showing repetitive or simple commands
- **Use `#pause`** between related commands to give viewers time to read the output
- **Use `#clear`** to reset the screen between sections
- **Script mode** is almost always better than interactive for final recordings — you can rehearse and get it right, and there's no risk of typos
- **Interactive mode** is great for live presentations or quick demos where you want flexibility
- Start your recording, then launch Typesmith — the screen clear gives you a clean starting frame
