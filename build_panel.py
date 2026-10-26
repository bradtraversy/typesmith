"""Build the local macOS app with system tools and no package dependencies."""

from pathlib import Path
import plistlib
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent
APP = ROOT / "build/TypeSmith.app"
CONTENTS = APP / "Contents"
RESOURCES = CONTENTS / "Resources"


def main():
    (CONTENTS / "MacOS").mkdir(parents=True, exist_ok=True)
    (RESOURCES / "python").mkdir(parents=True, exist_ok=True)
    (RESOURCES / "panel").mkdir(parents=True, exist_ok=True)
    for name in ("typesmith.py", "macos_hotkey.py", "project_store.py", "panel_backend.py", "live_speed.py"):
        shutil.copy2(ROOT / name, RESOURCES / "python" / name)
    for name in ("index.html", "style.css", "app.js"):
        shutil.copy2(ROOT / "panel" / name, RESOURCES / "panel" / name)
    with (CONTENTS / "Info.plist").open("wb") as output:
        plistlib.dump({"CFBundleName": "TypeSmith", "CFBundleDisplayName": "TypeSmith",
                      "CFBundleIdentifier": "dev.typesmith.panel", "CFBundleVersion": "1",
                      "CFBundleShortVersionString": "0.1.0", "CFBundleExecutable": "TypeSmith",
                      "CFBundlePackageType": "APPL", "NSHighResolutionCapable": True,
                      "LSMinimumSystemVersion": "13.0"}, output)
    subprocess.run(["xcrun", "swiftc", str(ROOT / "panel/App.swift"), str(ROOT / "panel/LiveSpeedPanel.swift"), "-o", str(CONTENTS / "MacOS/TypeSmith"),
                    "-framework", "Cocoa", "-framework", "WebKit"], check=True)
    subprocess.run(["codesign", "--force", "--sign", "-", str(APP)], check=True)
    print(APP)


if __name__ == "__main__":
    main()
