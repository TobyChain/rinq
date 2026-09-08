import Foundation

@MainActor
final class Store: ObservableObject {
    @Published var status: Status?
    @Published var settings: SettingsInfo?
    @Published var drafts: [String: String] = [:]
    @Published var saving = false

    let port: Int
    private var base: String { "http://127.0.0.1:\(port)" }

    init(port: Int = Int(ProcessInfo.processInfo.environment["RINQ_PORT"] ?? "7788") ?? 7788) {
        self.port = port
    }

    func refresh() async {
        async let s: Status? = fetch("/status")
        async let c: SettingsInfo? = fetch("/config")
        status = await s
        settings = await c
    }

    func keyDraft(_ id: String) -> String { drafts[id] ?? "" }

    func setDraft(_ id: String, _ v: String) { drafts[id] = v }

    func vendor(_ id: String) -> VendorInfo? {
        settings?.vendors.first { $0.id == id }
    }

    func toggle(_ vendor: VendorInfo) async {
        await patch([
            "enabled": Dictionary(uniqueKeysWithValues: settings!.vendors.map {
                ($0.id, $0.id == vendor.id ? !$0.enabled : $0.enabled)
            })
        ])
    }

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

    func moveRing(id ringId: String, direction: Int) async {
        guard let rings = status?.rings else { return }
        var ids = rings.map(\.id)
        guard let idx = ids.firstIndex(of: ringId) else { return }
        let target = idx + direction
        guard target >= 0, target < ids.count else { return }
        ids.swapAt(idx, target)
        await patch(["ringOrder": ids])
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

    private func fetch<T: Decodable>(_ path: String) async -> T? {
        guard let url = URL(string: "\(base)\(path)") else { return nil }
        do {
            let (data, resp) = try await URLSession.shared.data(from: url)
            guard let http = resp as? HTTPURLResponse, http.statusCode == 200 else { return nil }
            return try? JSONDecoder().decode(T.self, from: data)
        } catch { return nil }
    }

    private struct ConfigResponse: Decodable { let config: SettingsInfo }
}
