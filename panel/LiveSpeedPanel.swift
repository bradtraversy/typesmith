import Cocoa
import Darwin

final class LiveSpeedController: NSObject, NSWindowDelegate {
    private let panel: NSPanel
    private let slider = NSSlider(value: 120, minValue: 1, maxValue: 500, target: nil, action: nil)
    private let valueLabel = NSTextField(labelWithString: "120 chars/sec")
    private let statusLabel = NSTextField(labelWithString: "Start a step with Command + Option + T")
    private let stopButton = NSButton(title: "Stop", target: nil, action: nil)
    private var activity: NSObjectProtocol?
    private var timer: Timer?
    private var activeToken: String?
    private var pendingValue: (token: String, speed: Int)?
    private var feedback: String?
    private let cache = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Caches/typesmith")

    override init() {
        panel = NSPanel(contentRect: NSRect(x: 0, y: 0, width: 360, height: 142), styleMask: [.titled, .closable, .utilityWindow], backing: .buffered, defer: false)
        super.init()
        panel.delegate = self
        panel.title = "TypeSmith Live speed"
        panel.level = .floating
        panel.isFloatingPanel = true
        panel.becomesKeyOnlyIfNeeded = false
        panel.hidesOnDeactivate = false
        panel.canHide = false
        panel.isReleasedWhenClosed = false
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        let content = NSView(frame: NSRect(x: 0, y: 0, width: 360, height: 142))
        let title = NSTextField(labelWithString: "Live speed")
        title.font = .systemFont(ofSize: 13, weight: .semibold)
        title.frame = NSRect(x: 18, y: 108, width: 120, height: 18)
        valueLabel.font = .monospacedDigitSystemFont(ofSize: 12, weight: .medium)
        valueLabel.alignment = .right
        valueLabel.frame = NSRect(x: 200, y: 108, width: 140, height: 18)
        slider.frame = NSRect(x: 16, y: 69, width: 328, height: 26)
        slider.isContinuous = true
        slider.target = self
        slider.action = #selector(speedChanged(_:))
        slider.setAccessibilityLabel("Live typing speed")
        slider.toolTip = "Changes only the current take. Return to your editor to resume typing."
        statusLabel.font = .systemFont(ofSize: 10)
        statusLabel.textColor = .secondaryLabelColor
        statusLabel.frame = NSRect(x: 18, y: 42, width: 324, height: 16)
        let scopeLabel = NSTextField(labelWithString: "Current take only")
        scopeLabel.font = .systemFont(ofSize: 10)
        scopeLabel.textColor = .secondaryLabelColor
        scopeLabel.frame = NSRect(x: 18, y: 14, width: 160, height: 16)
        stopButton.frame = NSRect(x: 269, y: 8, width: 75, height: 28)
        stopButton.bezelStyle = .rounded
        stopButton.target = self
        stopButton.action = #selector(stopTyping(_:))
        for view in [title, valueLabel, slider, statusLabel, scopeLabel, stopButton] { content.addSubview(view) }
        panel.contentView = content
        if let screen = NSScreen.main {
            let visible = screen.visibleFrame
            panel.setFrameOrigin(NSPoint(x: visible.maxX - 384, y: visible.maxY - 205))
        }
        panel.setFrameAutosaveName("TypeSmithLiveSpeed")
        slider.isEnabled = false
        stopButton.isEnabled = false
        let pollTimer = Timer(timeInterval: 0.1, repeats: true) { [weak self] _ in self?.refresh() }
        RunLoop.main.add(pollTimer, forMode: .common)
        timer = pollTimer
    }

    func show(on screen: NSScreen? = nil) {
        if activity == nil {
            activity = ProcessInfo.processInfo.beginActivity(options: .userInitiatedAllowingIdleSystemSleep,
                reason: "Keep live typing controls responsive while another app is active")
        }
        refresh()
        // Recover a hidden app or a saved position on another display.
        if NSApp.isHidden { NSApp.unhideWithoutActivation() }
        if let screen = screen ?? NSScreen.main ?? NSScreen.screens.first {
            let visible = screen.visibleFrame
            panel.setFrameOrigin(NSPoint(x: visible.maxX - panel.frame.width - 24,
                                         y: visible.maxY - panel.frame.height - 24))
        }
        panel.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    func windowWillClose(_ notification: Notification) {
        if let activity = activity {
            ProcessInfo.processInfo.endActivity(activity)
            self.activity = nil
        }
    }

    private func activeLockIsHeld() -> Bool {
        let fd = open(cache.appendingPathComponent("hotkey.lock").path, O_RDWR)
        guard fd >= 0 else { return false }
        defer { close(fd) }
        if flock(fd, LOCK_EX | LOCK_NB) == 0 {
            flock(fd, LOCK_UN)
            return false
        }
        return errno == EWOULDBLOCK
    }

    private func liveTake() -> (token: String, initialSpeed: Double)? {
        guard activeLockIsHeld(),
              let data = try? Data(contentsOf: cache.appendingPathComponent("live-take.json")),
              let value = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let token = value["token"] as? String,
              token.count == 32, token.utf8.allSatisfy({ (48...57).contains($0) || (97...102).contains($0) }),
              let speed = value["initialSpeed"] as? Double,
              speed.isFinite, (1...500).contains(speed) else { return nil }
        return (token, speed)
    }

    private func speedURL(_ token: String) -> URL {
        cache.appendingPathComponent("speed-\(token).txt")
    }

    private func withControlLock(_ action: () -> Void) -> Bool {
        let fd = open(cache.appendingPathComponent("hotkey.control.lock").path, O_RDWR)
        guard fd >= 0 else { return false }
        defer { close(fd) }
        guard flock(fd, LOCK_EX | LOCK_NB) == 0 else { return false }
        defer { flock(fd, LOCK_UN) }
        action()
        return true
    }

    private func applyPending() {
        guard let update = pendingValue else { return }
        _ = withControlLock {
            guard liveTake()?.token == update.token else { pendingValue = nil; return }
            do {
                try String(update.speed).write(to: speedURL(update.token), atomically: true, encoding: .utf8)
                pendingValue = nil
                feedback = nil
                statusLabel.stringValue = "Return to your editor to resume typing."
            } catch {
                pendingValue = nil
                feedback = "Could not update speed. Try moving the slider again."
                statusLabel.stringValue = feedback!
            }
        }
    }

    private func refresh() {
        guard let take = liveTake() else {
            activeToken = nil
            pendingValue = nil
            feedback = nil
            slider.isEnabled = false
            stopButton.isEnabled = false
            statusLabel.stringValue = "Start a step with Command + Option + T"
            return
        }
        if activeToken != take.token { feedback = nil }
        activeToken = take.token
        applyPending()
        slider.isEnabled = true
        stopButton.isEnabled = true
        if pendingValue == nil {
            let stored = (try? String(contentsOf: speedURL(take.token), encoding: .utf8)).flatMap { Double($0) }
            let speed = stored.flatMap { $0.isFinite && (1...500).contains($0) ? $0 : nil } ?? take.initialSpeed
            slider.doubleValue = speed
            valueLabel.stringValue = "\(Int(speed.rounded())) chars/sec"
        }
        statusLabel.stringValue = feedback ?? "Return to your editor to resume typing."
    }

    @objc private func speedChanged(_ sender: NSSlider) {
        guard let token = activeToken else { return }
        let speed = max(1, min(500, Int(sender.doubleValue.rounded())))
        feedback = nil
        pendingValue = (token, speed)
        valueLabel.stringValue = "\(speed) chars/sec"
        applyPending()
    }

    @objc private func stopTyping(_ sender: NSButton) {
        guard let token = activeToken else { return }
        let written = withControlLock {
            guard liveTake()?.token == token else { return }
            do {
                try token.write(to: cache.appendingPathComponent("hotkey.cancel"), atomically: true, encoding: .utf8)
                feedback = "Stopping typing"
            } catch {
                feedback = "Use Escape to stop typing."
            }
        }
        if !written { feedback = "Use Escape to stop typing." }
        statusLabel.stringValue = feedback ?? "Use Escape to stop typing."
    }
}
