import Cocoa

let destination = URL(fileURLWithPath: CommandLine.arguments[1])
let iconset = destination.appendingPathComponent("TypeSmith.iconset")
try FileManager.default.createDirectory(at: iconset, withIntermediateDirectories: true)

func render(_ size: Int, template: Bool = false) -> Data {
    let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: size, pixelsHigh: size, bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: bitmap)
    let scale = CGFloat(size) / 1024
    let transform = NSAffineTransform()
    transform.scale(by: scale)
    transform.concat()
    if !template {
        NSColor(calibratedRed: 0.89, green: 0.914, blue: 0.953, alpha: 1).setFill()
        NSBezierPath(roundedRect: NSRect(x: 32, y: 32, width: 960, height: 960), xRadius: 210, yRadius: 210).fill()
    }
    (template ? NSColor.black : NSColor(calibratedRed: 0.157, green: 0.298, blue: 0.51, alpha: 1)).setFill()
    NSBezierPath(rect: NSRect(x: 200, y: 660, width: 440, height: 105)).fill()
    NSBezierPath(rect: NSRect(x: 367, y: 290, width: 106, height: 400)).fill()
    (template ? NSColor.black : NSColor(calibratedRed: 0.329, green: 0.482, blue: 0.725, alpha: 1)).setFill()
    NSBezierPath(rect: NSRect(x: 560, y: 267, width: 266, height: 96)).fill()
    NSGraphicsContext.restoreGraphicsState()
    return bitmap.representation(using: .png, properties: [:])!
}
for size in [16, 32, 128, 256, 512] {
    try render(size).write(to: iconset.appendingPathComponent("icon_\(size)x\(size).png"))
    try render(size * 2).write(to: iconset.appendingPathComponent("icon_\(size)x\(size)@2x.png"))
}
try render(128).write(to: destination.appendingPathComponent("logo.png"))
try render(36, template: true).write(to: destination.appendingPathComponent("MenuBarTemplate.png"))
