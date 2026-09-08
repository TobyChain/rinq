// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "RinqMenu",
    platforms: [.macOS(.v13)],
    targets: [
        .executableTarget(
            name: "RinqMenu",
            path: "Sources/RinqMenu",
            linkerSettings: [.linkedFramework("AppKit"), .linkedFramework("WebKit")]
        )
    ]
)
