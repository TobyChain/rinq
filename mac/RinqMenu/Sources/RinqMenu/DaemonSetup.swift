import Foundation

// First-run daemon bootstrap for the .app (DMG) distribution.
//
// Repo installs (install.sh) keep owning the daemon: install.sh never writes
// the `.app-managed` marker, so an installed-and-running repo daemon is left
// alone. A DMG-only machine has no daemon; the app bundles the Python runtime
// and an installer script in Contents/Resources and runs them when needed, so
// dragging the app into /Applications is a complete install.
//
// Install decision:
//   - marker present with a different version -> upgrade (app-managed only)
//   - daemon answers on the status port       -> nothing to do
//   - otherwise (fresh machine, or app-managed daemon that died) -> install
// A marker-less machine whose daemon is deliberately stopped still gets the
// install; a running menu-bar app without a daemon is useless anyway.
enum DaemonSetup {
    private static let markerRelativePath = ".rinq/libexec/rinq/.app-managed"
    private static let probeTimeout: TimeInterval = 1.5
    private static let postInstallWaitSeconds: Double = 8
    /// Installer stdout/stderr land here so a failed bootstrap on a DMG-only
    /// machine (missing python3, launchd refusal) is diagnosable; the app
    /// itself only shows the normal not-connected state.
    private static let installerLogRelative = "Library/Logs/rinq-app-install.log"

    static func ensureDaemon(port: Int) async {
        // Bare `swift run`/launchd-binary runs have no Info.plist version and
        // no bundled installer; repo installs are the intended path there.
        guard let script = Bundle.main.url(forResource: "install-daemon", withExtension: "sh"),
              let version = appVersion() else { return }
        if managedDaemonVersion() == nil || managedDaemonVersion() == version {
            if await daemonResponds(onPort: port) { return }
        }
        await runInstaller(script, version: version, port: port)
        await waitForDaemon(onPort: port)
    }

    private static func appVersion() -> String? {
        let v = Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString")
            as? String
        guard let v, !v.isEmpty else { return nil }
        return v
    }

    private static func managedDaemonVersion() -> String? {
        let url = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(markerRelativePath)
        guard let data = try? Data(contentsOf: url) else { return nil }
        let v = String(data: data, encoding: .utf8)?
            .trimmingCharacters(in: .whitespacesAndNewlines)
        return (v?.isEmpty == false) ? v : nil
    }

    private static func daemonResponds(onPort port: Int) async -> Bool {
        guard let url = URL(string: "http://127.0.0.1:\(port)/status") else { return false }
        var request = URLRequest(url: url)
        request.timeoutInterval = probeTimeout
        return await withCheckedContinuation { continuation in
            URLSession.shared.dataTask(with: request) { _, response, _ in
                // Any HTTP answer means a daemon is alive; connection errors
                // (refused, timeout) surface as a nil response.
                continuation.resume(returning: (response as? HTTPURLResponse) != nil)
            }.resume()
        }
    }

    private static func runInstaller(_ script: URL, version: String, port: Int) async {
        await Task.detached(priority: .utility) {
            let process = Process()
            process.executableURL = URL(fileURLWithPath: "/bin/bash")
            process.arguments = [script.path, version, String(port)]
            process.environment = ProcessInfo.processInfo.environment
            let log = Self.installerLogHandle()
            if let log {
                process.standardOutput = log
                process.standardError = log
            }
            do {
                try process.run()
                process.waitUntilExit()
                if process.terminationStatus != 0 {
                    Self.logInstallerNote(
                        "install-daemon.sh exited \(process.terminationStatus)", log: log
                    )
                }
            } catch {
                Self.logInstallerNote("could not launch installer: \(error)", log: log)
            }
        }.value
    }

    private static func installerLogHandle() -> FileHandle? {
        let fm = FileManager.default
        let url = fm.homeDirectoryForCurrentUser.appendingPathComponent(installerLogRelative)
        if !fm.fileExists(atPath: url.path) {
            try? fm.createDirectory(
                at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
            fm.createFile(atPath: url.path, contents: nil)
        }
        guard let handle = try? FileHandle(forWritingTo: url) else { return nil }
        try? handle.seekToEnd()
        return handle
    }

    private static func logInstallerNote(_ line: String, log: FileHandle?) {
        let stamped = Data(
            "[\(Int(Date().timeIntervalSince1970))] \(line)\n".utf8)
        log?.write(stamped)
    }

    private static func waitForDaemon(onPort port: Int) async {
        // launchd needs a moment to bootstrap the agent and start python.
        let deadline = Date().addingTimeInterval(postInstallWaitSeconds)
        while Date() < deadline {
            if await daemonResponds(onPort: port) { return }
            try? await Task.sleep(nanoseconds: 500_000_000)
        }
    }
}
