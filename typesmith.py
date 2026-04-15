#!/usr/bin/env python3
"""Typesmith - Terminal auto-typer for tutorial recording."""

import argparse
import os
import random
import subprocess
import sys
import termios
import time
import tty


def type_text(text, speed=12, variance=0.4):
    """Type text character by character with natural variable speed."""
    base_delay = 1.0 / speed
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        delay = max(0.005, random.gauss(base_delay, base_delay * variance))
        # Extra pause after word boundaries (scales with speed)
        if char == " ":
            delay += random.uniform(0.3, 1.0) * base_delay
        # Slightly longer after punctuation
        elif char in ".,;:!?":
            delay += random.uniform(0.5, 1.5) * base_delay
        # Occasional "think" pause (~2% chance)
        elif random.random() < 0.02:
            delay += random.uniform(2.0, 5.0) * base_delay
        time.sleep(delay)


def get_single_key():
    """Read a single keypress without echoing it."""
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    return ch


def parse_script(filepath):
    """Parse a script file into a list of actions.

    Returns a list of tuples: ('command', text) or ('directive', name, value).
    """
    actions = []
    with open(filepath) as f:
        for line in f:
            line = line.rstrip("\n")
            # Skip empty lines and pure comments
            if not line or line.lstrip().startswith("# "):
                continue
            # Directives: #speed, #pause, #prompt, #clear, #wait
            if line.lstrip().startswith("#"):
                stripped = line.lstrip()[1:]  # remove the #
                # Remove inline comments from directives
                if " #" in stripped:
                    stripped = stripped[: stripped.index(" #")]
                parts = stripped.strip().split(None, 1)
                if parts:
                    name = parts[0].lower()
                    value = parts[1] if len(parts) > 1 else ""
                    actions.append(("directive", name, value))
                continue
            actions.append(("command", line))
    return actions


def run_script(filepath, speed, variance, execute, prompt_str):
    """Run commands from a script file, typing each one on keypress."""
    actions = parse_script(filepath)
    current_speed = speed
    current_prompt = prompt_str

    commands = []
    pending_directives = []

    # Group directives with the command that follows them
    for action in actions:
        if action[0] == "directive":
            pending_directives.append(action)
        else:
            commands.append((pending_directives[:], action[1]))
            pending_directives = []

    if not commands:
        print("No commands found in script.")
        return

    # Clear screen so recording starts clean
    os.system("clear")

    for directives, cmd in commands:
        # Process directives before this command
        for _, name, value in directives:
            if name == "speed":
                current_speed = float(value)
            elif name == "pause":
                time.sleep(float(value))
            elif name == "prompt":
                current_prompt = value.strip() + " "
            elif name == "clear":
                os.system("clear")

        # Wait for keypress
        key = get_single_key()
        if key in ("\x03", "q"):  # Ctrl+C or q
            print("\n")
            return

        # Type the prompt + command
        sys.stdout.write(current_prompt)
        sys.stdout.flush()
        type_text(cmd, speed=current_speed, variance=variance)
        sys.stdout.write("\n")
        sys.stdout.flush()

        # Execute if requested
        if execute:
            subprocess.run(cmd, shell=True)

    print()


def run_interactive(speed, variance, execute, prompt_str):
    """Interactive mode: user types commands, they get re-typed with effect."""
    # Clear screen so recording starts clean
    os.system("clear")

    while True:
        try:
            # Read command from user (shown as they type)
            user_input = input(f"\033[90m(input)\033[0m ")
            if not user_input.strip():
                continue

            # Handle inline directives
            if user_input.startswith("#"):
                parts = user_input[1:].strip().split(None, 1)
                if parts:
                    name = parts[0].lower()
                    value = parts[1] if len(parts) > 1 else ""
                    if name == "speed":
                        speed = float(value)
                        print(f"  Speed set to {speed} cps")
                    elif name == "clear":
                        os.system("clear")
                    elif name == "prompt":
                        prompt_str = value.strip() + " "
                        print(f"  Prompt set to: {prompt_str!r}")
                    elif name == "pause":
                        time.sleep(float(value))
                continue

            # Move cursor up to overwrite the input line, then clear it
            sys.stdout.write("\033[A\033[2K")
            sys.stdout.flush()

            # Re-type with effect
            sys.stdout.write(prompt_str)
            sys.stdout.flush()
            type_text(user_input, speed=speed, variance=variance)
            sys.stdout.write("\n")
            sys.stdout.flush()

            # Execute if requested
            if execute:
                subprocess.run(user_input, shell=True)

        except (KeyboardInterrupt, EOFError):
            print("\n")
            break


def main():
    parser = argparse.ArgumentParser(
        prog="typesmith",
        description="Terminal auto-typer for tutorial recording.",
    )
    parser.add_argument(
        "-s", "--speed",
        type=float, default=12,
        help="Base typing speed in characters/sec (default: 12)",
    )
    parser.add_argument(
        "--execute", "-x",
        action="store_true",
        help="Execute commands after typing them",
    )
    parser.add_argument(
        "-p", "--prompt",
        default="$ ",
        help='Shell prompt string (default: "$ ")',
    )
    parser.add_argument(
        "-v", "--variance",
        type=float, default=0.4,
        help="Speed variance 0.0-1.0 (default: 0.4)",
    )

    subparsers = parser.add_subparsers(dest="mode")

    run_parser = subparsers.add_parser("run", help="Run commands from a script file")
    run_parser.add_argument("script", help="Path to script file")
    run_parser.add_argument("-s", "--speed", type=float, default=12,
                            help="Base typing speed in characters/sec (default: 12)")
    run_parser.add_argument("--execute", "-x", action="store_true",
                            help="Execute commands after typing them")
    run_parser.add_argument("-p", "--prompt", default="$ ",
                            help='Shell prompt string (default: "$ ")')
    run_parser.add_argument("-v", "--variance", type=float, default=0.4,
                            help="Speed variance 0.0-1.0 (default: 0.4)")

    args = parser.parse_args()

    execute = args.execute

    if args.mode == "run":
        run_script(args.script, args.speed, args.variance, execute, args.prompt)
    else:
        run_interactive(args.speed, args.variance, execute, args.prompt)


if __name__ == "__main__":
    main()
