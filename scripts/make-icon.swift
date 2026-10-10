// Regenerates mac/RinqMenu/Resources/AppIcon.icns.
// Run from the repo root: swift scripts/make-icon.swift
// Draws the menu-bar stacked-bars motif at every required size, then packs
// the iconset with iconutil. No external dependencies beyond macOS tooling.
import AppKit

let palette: [NSColor] = [
    NSColor(calibratedRed: 0.00, green: 0.52, blue: 1.00, alpha: 1),
    NSColor(calibratedRed: 0.53, green: 0.37, blue: 1.00, alpha: 1),
    NSColor(calibratedRed: 0.08, green: 0.82, blue: 0.40, alpha: 1),
    NSColor(calibratedRed: 1.00, green: 0.58, blue: 0.04, alpha: 1),
]
let fills: [CGFloat] = [0.78, 0.46, 0.92, 0.30]

func drawIcon(size: CGFloat) -> NSImage {
    let image = NSImage(size: NSSize(width: size, height: size))
    image.lockFocus()
    let full = NSRect(x: 0, y: 0, width: size, height: size)

    // macOS-style rounded-square plate.
    NSColor(calibratedWhite: 0.12, alpha: 1).setFill()
    NSBezierPath(roundedRect: full.insetBy(dx: size * 0.04, dy: size * 0.04),
                 xRadius: size * 0.225, yRadius: size * 0.225).fill()

    // Four stacked quota bars, mirroring the menu-bar item.
    let barArea = full.insetBy(dx: size * 0.22, dy: size * 0.24)
    let barHeight = barArea.height * 0.14
    let gap = barArea.height * 0.068
    for (i, fill) in fills.enumerated() {
        let y = barArea.maxY - barHeight - CGFloat(i) * (barHeight + gap)
        let color = palette[i % palette.count]
        let track = NSRect(x: barArea.minX, y: y, width: barArea.width, height: barHeight)
        color.withAlphaComponent(0.32).setFill()
        NSBezierPath(roundedRect: track, xRadius: barHeight / 2, yRadius: barHeight / 2).fill()
        let fillRect = NSRect(
            x: track.minX, y: track.minY,
            width: max(barHeight, track.width * fill), height: track.height
        )
        color.setFill()
        NSBezierPath(roundedRect: fillRect, xRadius: barHeight / 2, yRadius: barHeight / 2).fill()
    }
    image.unlockFocus()
    return image
}

func writePNG(_ image: NSImage, pixels: Int, to url: URL) throws {
    guard let rep = NSBitmapImageRep(
        bitmapDataPlanes: nil, pixelsWide: pixels, pixelsHigh: pixels,
        bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
        colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0
    ) else { throw NSError(domain: "icon", code: 1) }
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
    image.draw(in: NSRect(x: 0, y: 0, width: pixels, height: pixels))
    NSGraphicsContext.restoreGraphicsState()
    guard let data = rep.representation(using: .png, properties: [:]) else {
        throw NSError(domain: "icon", code: 2)
    }
    try data.write(to: url)
}

let repoRoot = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent()
let iconset = FileManager.default.temporaryDirectory
    .appendingPathComponent("rinq-icon.iconset", isDirectory: true)
try? FileManager.default.removeItem(at: iconset)
try FileManager.default.createDirectory(at: iconset, withIntermediateDirectories: true)

let entries: [(name: String, pixels: Int)] = [
    ("icon_16x16.png", 16), ("icon_16x16@2x.png", 32),
    ("icon_32x32.png", 32), ("icon_32x32@2x.png", 64),
    ("icon_128x128.png", 128), ("icon_128x128@2x.png", 256),
    ("icon_256x256.png", 256), ("icon_256x256@2x.png", 512),
    ("icon_512x512.png", 512), ("icon_512x512@2x.png", 1024),
]
for entry in entries {
    let image = drawIcon(size: CGFloat(entry.pixels))
    try writePNG(image, pixels: entry.pixels, to: iconset.appendingPathComponent(entry.name))
}

let icns = repoRoot.appendingPathComponent("mac/RinqMenu/Resources/AppIcon.icns")
try? FileManager.default.createDirectory(
    at: icns.deletingLastPathComponent(), withIntermediateDirectories: true)
let process = Process()
process.executableURL = URL(fileURLWithPath: "/usr/bin/iconutil")
process.arguments = ["-c", "icns", iconset.path, "-o", icns.path]
process.launch()
process.waitUntilExit()
guard process.terminationStatus == 0 else {
    FileHandle.standardError.write("iconutil failed\n".data(using: .utf8)!)
    exit(1)
}
print("wrote \(icns.path)")
