import Foundation

/// Fetches per-vendor quota rings directly from each provider. No Mac relay.
/// Each call tolerates missing keys and unexpected shapes, returning either
/// the parsed rings or an empty array so the aggregator can skip it.
enum TRProviders {

    static func fetchAll(using settings: TRSettings) async -> TRStatus {
        let enabled = settings.enabledVendors
        var rings: [TRRing] = []

        await withTaskGroup(of: [TRRing].self) { group in
            for vendor in TRVendor.allCases where enabled.contains(vendor) {
                group.addTask { await ringsFor(vendor, settings: settings) }
            }
            for await vendorRings in group {
                rings.append(contentsOf: vendorRings)
            }
        }

        let status = TRStatus(version: 1, updatedAt: Int(Date().timeIntervalSince1970), rings: rings)
        TRStatusCache.shared.store(status)
        return status
    }

    static func ringsFor(_ vendor: TRVendor, settings: TRSettings) async -> [TRRing] {
        let key = settings.key(vendor)
        switch vendor {
        case .chatgpt:
            return await fetchChatGPT(token: key, account: settings.chatGPTAccountId)
        case .minimax:
            return key.isEmpty ? [] : await fetchMiniMax(key: key)
        case .deepseek:
            return key.isEmpty ? [] : await fetchDeepSeek(key: key)
        case .moonshot:
            return key.isEmpty ? [] : await fetchMoonshot(key: key)
        case .zhipu:
            return key.isEmpty ? [] : await fetchZhipu(key: key)
        case .openai:
            return key.isEmpty ? [] : await fetchOpenAISpend(key: key)
        }
    }

    // MARK: - HTTP

    private static func getJSON(_ url: String, headers: [String: String]) async -> [String: Any]? {
        guard let u = URL(string: url) else { return nil }
        var req = URLRequest(url: u)
        req.timeoutInterval = 20
        req.setValue("application/json", forHTTPHeaderField: "Accept")
        for (k, v) in headers { req.setValue(v, forHTTPHeaderField: k) }
        do {
            let (data, resp) = try await URLSession.shared.data(for: req)
            guard let http = resp as? HTTPURLResponse, (200...299).contains(http.statusCode) else { return nil }
            return try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        } catch {
            return nil
        }
    }

    private static func int(_ any: Any?) -> Int? {
        if let i = any as? Int { return i }
        if let d = any as? Double { return Int(d) }
        if let s = any as? String, let d = Double(s) { return Int(d) }
        return nil
    }

    private static func double(_ any: Any?) -> Double? {
        if let d = any as? Double { return d }
        if let i = any as? Int { return Double(i) }
        if let s = any as? String { return Double(s) }
        return nil
    }

    // MARK: - ChatGPT / Codex (unofficial subscription usage)

    private static func fetchChatGPT(token: String, account: String) async -> [TRRing] {
        guard !token.isEmpty else { return [] }
        var headers = ["Authorization": "Bearer \(token)"]
        if !account.isEmpty { headers["ChatGPT-Account-Id"] = account }
        guard let json = await getJSON("https://chatgpt.com/backend-api/wham/usage", headers: headers),
              let rl = json["rate_limit"] as? [String: Any] else { return [] }

        var rings: [TRRing] = []
        if let primary = rl["primary_window"] as? [String: Any] {
            rings.append(TRRing(
                id: "codex-5h", label: "Codex 5h", vendor: "codex", kind: "window",
                usedPercent: int(primary["used_percent"]).map(clamp),
                remainingPercent: nil, remaining: nil, currency: nil,
                resetsAt: int(primary["reset_at"]),
                windowMins: int(primary["limit_window_seconds"]).map { $0 / 60 },
                accent: "blue", spentUsd: nil, budgetUsd: nil, status: nil))
        }
        if let secondary = rl["secondary_window"] as? [String: Any] {
            rings.append(TRRing(
                id: "codex-week", label: "Codex week", vendor: "codex", kind: "window",
                usedPercent: int(secondary["used_percent"]).map(clamp),
                remainingPercent: nil, remaining: nil, currency: nil,
                resetsAt: int(secondary["reset_at"]),
                windowMins: int(secondary["limit_window_seconds"]).map { $0 / 60 },
                accent: "indigo", spentUsd: nil, budgetUsd: nil, status: nil))
        }
        return rings
    }

    // MARK: - MiniMax coding plan

    private static func fetchMiniMax(key: String) async -> [TRRing] {
        guard let json = await getJSON("https://api.minimaxi.com/v1/api/openplatform/coding_plan/remains",
                                      headers: ["Authorization": "Bearer \(key)"]) else { return [] }
        let remains = (json["model_remains"] as? [[String: Any]]) ?? []
        guard let general = remains.first(where: { ($0["model_name"] as? String) == "general" }) else { return [] }
        let intervalRemaining = int(general["current_interval_remaining_percent"]) ?? 100
        let weeklyRemaining = int(general["current_weekly_remaining_percent"]) ?? 100
        return [
            TRRing(id: "minimax-5h", label: "MiniMax 5h", vendor: "minimax", kind: "window",
                   usedPercent: 100 - clamp(intervalRemaining), remainingPercent: nil, remaining: nil, currency: nil,
                   resetsAt: (int(general["end_time"])).map { $0 / 1000 }, windowMins: 300,
                   accent: "orange", spentUsd: nil, budgetUsd: nil, status: nil),
            TRRing(id: "minimax-week", label: "MiniMax week", vendor: "minimax", kind: "window",
                   usedPercent: 100 - clamp(weeklyRemaining), remainingPercent: nil, remaining: nil, currency: nil,
                   resetsAt: (int(general["weekly_end_time"])).map { $0 / 1000 }, windowMins: 10080,
                   accent: "red", spentUsd: nil, budgetUsd: nil, status: nil),
        ]
    }

    // MARK: - DeepSeek balance

    private static func fetchDeepSeek(key: String) async -> [TRRing] {
        guard let json = await getJSON("https://api.deepseek.com/user/balance",
                                      headers: ["Authorization": "Bearer \(key)"]) else { return [] }
        let infos = (json["balance_infos"] as? [[String: Any]]) ?? []
        let cny = infos.first(where: { ($0["currency"] as? String) == "CNY" }) ?? infos.first
        guard let balance = double(cny?["total_balance"]) else { return [] }
        return [TRRing(id: "deepseek-balance", label: "DeepSeek", vendor: "deepseek", kind: "balance",
                       usedPercent: nil, remainingPercent: nil, remaining: balance, currency: "CNY",
                       resetsAt: nil, windowMins: nil, accent: "teal",
                       spentUsd: nil, budgetUsd: nil, status: nil)]
    }

    // MARK: - Moonshot / Kimi (best effort)

    private static func fetchMoonshot(key: String) async -> [TRRing] {
        guard let json = await getJSON("https://api.moonshot.cn/v1/users/me/balance",
                                      headers: ["Authorization": "Bearer \(key)"]) else { return [] }
        let d = (json["data"] as? [String: Any]) ?? json
        guard let balance = double(d["available_balance"] ?? d["balance"] ?? d["total_balance"]) else { return [] }
        return [TRRing(id: "moonshot-balance", label: "Kimi", vendor: "moonshot", kind: "balance",
                       usedPercent: nil, remainingPercent: nil, remaining: balance, currency: "CNY",
                       resetsAt: nil, windowMins: nil, accent: "purple",
                       spentUsd: nil, budgetUsd: nil, status: nil)]
    }

    // MARK: - Zhipu / GLM (best effort)

    private static func fetchZhipu(key: String) async -> [TRRing] {
        guard let json = await getJSON("https://open.bigmodel.cn/api/monitor/usage/quota/limit",
                                      headers: ["Authorization": "Bearer \(key)"]) else { return [] }
        let d = (json["data"] as? [String: Any]) ?? json
        guard let balance = double(d["balance"] ?? d["available_balance"] ?? d["total_balance"]) else { return [] }
        return [TRRing(id: "zhipu-balance", label: "GLM", vendor: "zhipu", kind: "balance",
                       usedPercent: nil, remainingPercent: nil, remaining: balance, currency: "CNY",
                       resetsAt: nil, windowMins: nil, accent: "red",
                       spentUsd: nil, budgetUsd: nil, status: nil)]
    }

    // MARK: - OpenAI admin spend (best effort; sums month-to-date USD)

    private static func fetchOpenAISpend(key: String) async -> [TRRing] {
        let now = Date()
        let start = Calendar(identifier: .gregorian).date(from: Calendar(identifier: .gregorian)
            .dateComponents([.year, .month], from: now)) ?? now
        let startTs = Int(start.timeIntervalSince1970)
        let url = "https://api.openai.com/v1/organization/costs?start_time=\(startTs)&bucket_width=1d&limit=31"
        guard let json = await getJSON(url, headers: ["Authorization": "Bearer \(key)"]) else { return [] }
        var spent = 0.0
        for bucket in (json["data"] as? [[String: Any]]) ?? [] {
            for result in (bucket["results"] as? [[String: Any]]) ?? [] {
                if let amount = result["amount"] as? [String: Any],
                   (amount["currency"] as? String) == "usd" {
                    spent += double(amount["value"]) ?? 0
                }
            }
        }
        return [TRRing(id: "openai-api", label: "OpenAI API", vendor: "openai", kind: "budget",
                       usedPercent: nil, remainingPercent: nil, remaining: nil, currency: "USD",
                       resetsAt: nil, windowMins: nil, accent: "green",
                       spentUsd: spent, budgetUsd: nil, status: nil)]
    }

    private static func clamp(_ v: Int) -> Int { min(100, max(0, v)) }
}

/// Last fetched status, shared with the widget via the App Group defaults.
final class TRStatusCache {
    static let shared = TRStatusCache()
    private let defaults: UserDefaults
    private let key = "cachedStatus"

    init() {
        defaults = UserDefaults(suiteName: TRSettings.appGroup) ?? .standard
    }

    func store(_ status: TRStatus) {
        if let data = try? JSONEncoder().encode(status) {
            defaults.set(data, forKey: key)
        }
    }

    var cached: TRStatus? {
        guard let data = defaults.data(forKey: key) else { return nil }
        return try? JSONDecoder().decode(TRStatus.self, from: data)
    }
}
