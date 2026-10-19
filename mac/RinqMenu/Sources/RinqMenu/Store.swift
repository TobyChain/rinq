import Foundation

@MainActor
final class Store: ObservableObject {
    @Published var status: Status?
    @Published var settings: SettingsInfo?
    @Published var usage: UsageSummary?
    @Published var sessions: SessionSnapshot?
    @Published var alerts: [QuotaAlert] = []
    @Published var drafts: [String: String] = [:]
    @Published var saving = false

    let port: Int
    private var alertMonitor: QuotaAlertMonitor
    private var refreshingSessions = false
    private var base: String { "http://127.0.0.1:\(port)" }

    init(
        port: Int = Int(ProcessInfo.processInfo.environment["RINQ_PORT"] ?? "7788") ?? 7788,
        alertDefaults: UserDefaults = .standard
    ) {
        self.port = port
        alertMonitor = QuotaAlertMonitor(defaults: alertDefaults)
    }

    @discardableResult
    func refresh() async -> Bool {
        async let s: Status? = fetch("/status")
        async let c: SettingsInfo? = fetch("/config")
        async let u: UsageSummary? = fetch("/usage")
        async let sess: Void = refreshSessions()
        let fetchedStatus = await s
        status = fetchedStatus
        settings = await c
        usage = await u
        await sess
        guard let fetchedStatus else { return false }
        let evaluation = alertMonitor.evaluate(rings: fetchedStatus.rings)
        alerts = evaluation.active
        return evaluation.shouldPresent
    }

    /// Publish local activity independently of slow provider quota requests.
    func refreshSessions() async {
        guard !refreshingSessions else { return }
        refreshingSessions = true
        defer { refreshingSessions = false }
        let snapshot: SessionSnapshot? = await fetch("/sessions", timeout: 5)
        if !Task.isCancelled { sessions = snapshot }
    }

    func keyDraft(_ id: String) -> String { drafts[id] ?? "" }

    func setDraft(_ id: String, _ v: String) { drafts[id] = v }

    func saveKey(_ id: String) async {
        let key = (drafts[id] ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        guard !key.isEmpty else { return }
        saving = true
        await patch(["keys": [id: key]])
        drafts[id] = ""
        saving = false
    }

    func clearKey(_ id: String) async {
        await patch(["keys": [id: ""]])
    }

    /// Cancel or resume quota tracking for one vendor. The credential is kept.
    func setTracking(_ id: String, _ on: Bool) async {
        await patch(["tracking": [id: on]])
    }

    /// Cancel or resume monitoring for one local IDE.
    func setIntegrationMonitored(_ id: String, _ on: Bool) async {
        await patch(["monitored": [id: on]])
    }

    /// Rescan this Mac for local IDEs and republish the settings snapshot.
    func refreshIntegrations() async {
        if let rescan: SettingsInfo = await fetch("/config", timeout: 30) {
            settings = rescan
        }
    }

    func saveRingOrder(_ ids: [String]) async {
        await patch(["ringOrder": ids])
    }

    @discardableResult
    func dismissAlerts() -> Bool {
        guard !alerts.isEmpty else { return false }
        alertMonitor.dismiss(alertIDs: Set(alerts.map(\.id)))
        alerts = []
        return true
    }

    @discardableResult
    private func patch(_ body: [String: Any]) async -> SettingsInfo? {
        guard let url = URL(string: "\(base)/config"),
              let data = try? JSONSerialization.data(withJSONObject: body) else { return nil }
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = data
        do {
            let (respData, _) = try await URLSession.shared.data(for: req)
            if let wrapped = try? JSONDecoder().decode(ConfigResponse.self, from: respData) {
                settings = wrapped.config
                await reloadStatus()
                return wrapped.config
            }
        } catch {}
        return nil
    }

    private func reloadStatus() async {
        status = await fetch("/status")
    }

    private func fetch<T: Decodable>(_ path: String, timeout: TimeInterval = 60) async -> T? {
        guard let url = URL(string: "\(base)\(path)") else { return nil }
        var request = URLRequest(url: url)
        request.timeoutInterval = timeout
        do {
            let (data, resp) = try await URLSession.shared.data(for: request)
            guard let http = resp as? HTTPURLResponse, http.statusCode == 200 else { return nil }
            return try? JSONDecoder().decode(T.self, from: data)
        } catch { return nil }
    }

    private struct ConfigResponse: Decodable { let config: SettingsInfo }
}
