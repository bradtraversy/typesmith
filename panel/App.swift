import Cocoa
import WebKit
import UniformTypeIdentifiers

final class PanelController: NSObject, NSApplicationDelegate, NSWindowDelegate, WKScriptMessageHandler, WKNavigationDelegate {
    private var window: NSWindow!
    private var webView: WKWebView!
    private var dirty = false
    private var liveSpeed: LiveSpeedController!
    private let backendQueue = DispatchQueue(label: "dev.typesmith.backend")
    private let allowedActions: Set<String> = ["state", "save", "saveCopy", "open", "reset", "skip", "setNext", "stop"]
    private var pageURL: URL { Bundle.main.resourceURL!.appendingPathComponent("panel/index.html") }

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        NSApp.appearance = NSAppearance(named: .aqua)
        liveSpeed = LiveSpeedController()
        buildMenu()
        let configuration = WKWebViewConfiguration()
        configuration.userContentController.add(self, name: "typesmith")
        webView = WKWebView(frame: .zero, configuration: configuration)
        webView.navigationDelegate = self
        webView.setValue(false, forKey: "drawsBackground")
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1100, height: 790), styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        window.title = "TypeSmith"
        window.minSize = NSSize(width: 870, height: 680)
        window.isReleasedWhenClosed = false
        window.delegate = self
        window.contentView = webView
        window.center()
        window.setFrameAutosaveName("TypeSmithPanel")
        webView.loadFileURL(pageURL, allowingReadAccessTo: pageURL.deletingLastPathComponent())
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        window.makeKeyAndOrderFront(nil)
        return true
    }

    func windowShouldClose(_ sender: NSWindow) -> Bool {
        if !confirmDiscard() { return false }
        sender.orderOut(nil)
        return false
    }

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        return confirmDiscard() ? .terminateNow : .terminateCancel
    }

    private func confirmDiscard() -> Bool {
        if !dirty { return true }
        let alert = NSAlert()
        alert.messageText = "Close with unsaved changes?"
        alert.informativeText = "Save your recording first to keep these edits."
        alert.addButton(withTitle: "Keep editing")
        alert.addButton(withTitle: "Close")
        return alert.runModal() == .alertSecondButtonReturn
    }

    private func buildMenu() {
        let main = NSMenu()
        let appItem = NSMenuItem()
        let appMenu = NSMenu()
        appMenu.addItem(withTitle: "Hide TypeSmith", action: #selector(NSApplication.hide(_:)), keyEquivalent: "h")
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "Quit TypeSmith", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        appItem.submenu = appMenu
        main.addItem(appItem)
        let fileItem = NSMenuItem(title: "File", action: nil, keyEquivalent: "")
        let file = NSMenu(title: "File")
        for (title, command, key) in [("Open recording", "open", "o"), ("Save changes", "save", "s"), ("Save copy", "saveCopy", ""), ("Reload recording", "reload", "")] {
            let item = NSMenuItem(title: title, action: #selector(menuCommand(_:)), keyEquivalent: key)
            item.target = self
            item.representedObject = command
            file.addItem(item)
        }
        fileItem.submenu = file
        main.addItem(fileItem)
        let editItem = NSMenuItem(title: "Edit", action: nil, keyEquivalent: "")
        let edit = NSMenu(title: "Edit")
        for (title, selector, key) in [("Undo", "undo:", "z"), ("Cut", "cut:", "x"), ("Copy", "copy:", "c"), ("Paste", "paste:", "v"), ("Select All", "selectAll:", "a")] {
            edit.addItem(withTitle: title, action: Selector(selector), keyEquivalent: key)
        }
        editItem.submenu = edit
        main.addItem(editItem)
        NSApp.mainMenu = main
    }

    @objc private func menuCommand(_ sender: NSMenuItem) {
        guard let command = sender.representedObject as? String else { return }
        let data = try! JSONSerialization.data(withJSONObject: [command])
        let json = String(data: data, encoding: .utf8)!
        webView.evaluateJavaScript("window.panelCommand(\(json)[0])", completionHandler: nil)
    }

    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        decisionHandler(navigationAction.request.url?.standardizedFileURL == pageURL.standardizedFileURL ? .allow : .cancel)
    }

    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.frameInfo.isMainFrame,
              message.frameInfo.request.url?.standardizedFileURL == pageURL.standardizedFileURL,
              var request = message.body as? [String: Any],
              let id = request.removeValue(forKey: "id") as? String,
              let action = request["action"] as? String else { return }
        if action == "hide" {
            let screen = window.screen
            window.orderOut(nil)
            liveSpeed.show(on: screen)
            reply(id, ["ok": true, "data": [:]])
        } else if action == "liveSpeed" {
            liveSpeed.show(on: window.screen)
            reply(id, ["ok": true, "data": [:]])
        } else if action == "dirty" {
            dirty = request["value"] as? Bool ?? false
            window.isDocumentEdited = dirty
            reply(id, ["ok": true, "data": [:]])
        } else if allowedActions.contains(action) {
            if action == "open" || action == "saveCopy" {
                chooseFile(id, request: request, saving: action == "saveCopy")
            } else {
                runBackend(id, request: request)
            }
        } else {
            reply(id, ["ok": false, "error": "Unknown panel action."])
        }
    }

    private func chooseFile(_ id: String, request: [String: Any], saving: Bool) {
        let panel: NSSavePanel = saving ? NSSavePanel() : NSOpenPanel()
        panel.allowedContentTypes = [.json]
        panel.canCreateDirectories = saving
        if let current = request["path"] as? String {
            panel.directoryURL = URL(fileURLWithPath: current).deletingLastPathComponent()
        }
        if saving {
            let project = request["project"] as? [String: Any]
            let name = (project?["name"] as? String ?? "Recording").replacingOccurrences(of: "/", with: "-")
            panel.nameFieldStringValue = name + " copy.typesmith.json"
            panel.title = "Save a recording copy"
        } else if let open = panel as? NSOpenPanel {
            open.canChooseFiles = true
            open.canChooseDirectories = false
            open.allowsMultipleSelection = false
            open.title = "Open a TypeSmith recording"
        }
        panel.beginSheetModal(for: window) { [weak self] response in
            guard let self = self else { return }
            guard response == .OK, let url = panel.url else {
                self.reply(id, ["ok": true, "data": ["cancelled": true]])
                return
            }
            var selected = request
            selected["destination"] = url.path
            self.runBackend(id, request: selected)
        }
    }

    private func runBackend(_ id: String, request: [String: Any]) {
        backendQueue.async { [weak self] in
            guard let self = self else { return }
            var result: [String: Any]
            do {
                let process = Process()
                let input = Pipe()
                let output = Pipe()
                process.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
                process.arguments = [Bundle.main.resourceURL!.appendingPathComponent("python/panel_backend.py").path]
                process.standardInput = input
                process.standardOutput = output
                process.standardError = output
                try process.run()
                let data = try JSONSerialization.data(withJSONObject: request)
                input.fileHandleForWriting.write(data)
                try input.fileHandleForWriting.close()
                let response = output.fileHandleForReading.readDataToEndOfFile()
                process.waitUntilExit()
                if let parsed = try? JSONSerialization.jsonObject(with: response) as? [String: Any] {
                    result = parsed
                } else {
                    result = ["ok": false, "error": "TypeSmith could not read the recording. Check that macOS Python 3 is available."]
                }
            } catch {
                result = ["ok": false, "error": error.localizedDescription]
            }
            DispatchQueue.main.async { self.reply(id, result) }
        }
    }

    private func reply(_ id: String, _ result: [String: Any]) {
        guard let data = try? JSONSerialization.data(withJSONObject: [id, result]), let json = String(data: data, encoding: .utf8) else { return }
        webView.evaluateJavaScript("window.nativeReply(...\(json))", completionHandler: nil)
    }
}

@main
struct TypeSmithApp {
    static func main() {
        let application = NSApplication.shared
        let controller = PanelController()
        application.delegate = controller
        application.run()
    }
}
