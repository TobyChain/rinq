import Foundation

enum QuotaAlertLevel: String, Codable, Hashable {
    case warning
    case critical

    var priority: Int {
        switch self {
        case .warning: return 1
        case .critical: return 2
        }
    }
}

enum QuotaAlertReason: String, Codable, Hashable {
    case rapidUsage
    case lowQuota
    case exhausted
}

struct QuotaAlert: Codable, Identifiable, Hashable {
    let ringID: String
    let label: String
    let level: QuotaAlertLevel
    let reason: QuotaAlertReason
    let message: String

    var id: String { "\(ringID):\(reason.rawValue)" }
}

struct QuotaAlertEvaluation {
    let active: [QuotaAlert]
    let shouldPresent: Bool
}

private struct UsageSample: Codable {
    let usedPercent: Int
    let at: Date
}

struct QuotaAlertMonitor {
    private static let stateKey = "rinq.quota-alert-state.v1"
    private static let minimumRapidAge: TimeInterval = 25 * 60
    private static let maximumRapidAge: TimeInterval = 45 * 60
    private static let rapidIncrease = 20

    private struct State: Codable {
        var samples: [String: [UsageSample]] = [:]
        var activeAlertIDs: Set<String> = []
        var dismissedAlertIDs: Set<String>?
    }

    private let defaults: UserDefaults
    private var state: State

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        if let data = defaults.data(forKey: Self.stateKey),
           let stored = try? JSONDecoder().decode(State.self, from: data) {
            state = stored
        } else {
            state = State()
        }
    }

    mutating func evaluate(rings: [Ring], now: Date = Date()) -> QuotaAlertEvaluation {
        var active: [QuotaAlert] = []
        var currentSamples: [String: [UsageSample]] = [:]

        for ring in rings {
            guard let used = ring.usedPercent else { continue }
            let history = (state.samples[ring.id] ?? [])
                .filter { now.timeIntervalSince($0.at) <= Self.maximumRapidAge }
            currentSamples[ring.id] = history + [UsageSample(usedPercent: used, at: now)]
            if let alert = alert(for: ring, usedPercent: used, now: now) {
                active.append(alert)
            }
        }

        let detectedIDs = Set(active.map(\.id))
        let dismissedIDs = (state.dismissedAlertIDs ?? []).intersection(detectedIDs)
        let visible = active.filter { !dismissedIDs.contains($0.id) }
        let activeIDs = Set(visible.map(\.id))
        let shouldPresent = !activeIDs.subtracting(state.activeAlertIDs).isEmpty
        state.samples = currentSamples
        state.activeAlertIDs = activeIDs
        state.dismissedAlertIDs = dismissedIDs
        persist()
        return QuotaAlertEvaluation(
            active: visible.sorted { $0.level.priority > $1.level.priority },
            shouldPresent: shouldPresent
        )
    }

    mutating func dismiss(alertIDs: Set<String>) {
        var dismissed = state.dismissedAlertIDs ?? []
        dismissed.formUnion(alertIDs)
        state.dismissedAlertIDs = dismissed
        state.activeAlertIDs.subtract(alertIDs)
        persist()
    }

    private func alert(for ring: Ring, usedPercent: Int, now: Date) -> QuotaAlert? {
        let remaining = ring.remainingPercent ?? (100 - usedPercent)
        if usedPercent >= 100 || remaining <= 0 {
            return QuotaAlert(
                ringID: ring.id,
                label: ring.label,
                level: .critical,
                reason: .exhausted,
                message: "\(ring.label) quota exhausted"
            )
        }

        if let threshold = lowQuotaThreshold(for: ring), remaining < threshold {
            return QuotaAlert(
                ringID: ring.id,
                label: ring.label,
                level: .warning,
                reason: .lowQuota,
                message: "\(ring.label) has \(remaining)% remaining"
            )
        }

        guard let previous = state.samples[ring.id]?
            .filter({
                let age = now.timeIntervalSince($0.at)
                return age >= Self.minimumRapidAge && age <= Self.maximumRapidAge
            })
            .max(by: { $0.at < $1.at }) else { return nil }
        let increase = usedPercent - previous.usedPercent
        guard increase > Self.rapidIncrease else { return nil }
        return QuotaAlert(
            ringID: ring.id,
            label: ring.label,
            level: .warning,
            reason: .rapidUsage,
            message: "\(ring.label) used +\(increase)% in about 30 minutes"
        )
    }

    private func lowQuotaThreshold(for ring: Ring) -> Int? {
        guard ring.kind == "window", let windowMins = ring.windowMins else { return nil }
        if windowMins <= 300 { return 30 }
        if windowMins >= 10080 { return 10 }
        return nil
    }

    private func persist() {
        guard let data = try? JSONEncoder().encode(state) else { return }
        defaults.set(data, forKey: Self.stateKey)
    }
}
