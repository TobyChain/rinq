import Foundation
import SwiftUI

struct Ring: Codable, Identifiable, Hashable {
    let id: String
    let label: String
    let vendor: String?
    let kind: String?
    let usedPercent: Int?
    let remainingPercent: Int?
    let remaining: Double?
    let currency: String?
    let resetsAt: Int?
    let windowMins: Int?
    let accent: String?
    let spentUsd: Double?
    let budgetUsd: Double?
    let usedValue: Double?
    let totalValue: Double?
    let valueUnit: String?
    let status: String?
    let statusDetail: String?
}

enum RingOrder {
    static func moving(_ rings: [Ring], from source: Int, toDropRow dropRow: Int) -> [Ring] {
        guard rings.indices.contains(source), dropRow >= 0, dropRow <= rings.count else { return rings }
        var result = rings
        let moved = result.remove(at: source)
        let insertion = min(source < dropRow ? dropRow - 1 : dropRow, result.count)
        result.insert(moved, at: insertion)
        return result
    }
}

struct Status: Codable {
    let rings: [Ring]
    let updatedAt: Int?
}

struct VendorInfo: Codable, Identifiable, Hashable {
    let id: String
    let label: String
    let accent: String?
    let kind: String?
    var enabled: Bool
    let hasCredential: Bool
    let hasKeySet: Bool
}

struct IntegrationInfo: Codable, Identifiable, Hashable {
    let id: String
    let label: String
    let vendor: String
    let installed: Bool
    let configured: Bool
    let running: Bool
    let version: String?
    let bundleId: String?
    let appPath: String?
    let usageAvailable: Bool
    let usageAdapter: String?
    let authMethod: String
    let authState: String
    let planState: String
    let planReasons: [String]
    let quotaState: String
    let usageSupport: String?
    let quotaSupport: String?
    let connectURL: String
}

struct SettingsInfo: Codable {
    let ringOrder: [String]
    let vendors: [VendorInfo]
    let integrations: [IntegrationInfo]

    enum CodingKeys: String, CodingKey {
        case ringOrder, vendors, integrations
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        ringOrder = try container.decode([String].self, forKey: .ringOrder)
        vendors = try container.decode([VendorInfo].self, forKey: .vendors)
        integrations = try container.decodeIfPresent([IntegrationInfo].self, forKey: .integrations) ?? []
    }
}

struct UsageDay: Codable, Identifiable, Hashable {
    let date: String
    let inputTokens: Int
    let outputTokens: Int
    let cachedInputTokens: Int
    let cacheWriteInputTokens: Int
    let reasoningOutputTokens: Int
    let totalTokens: Int
    let requests: Int

    var id: String { date }
    var inputOutputTokens: Int { inputTokens + outputTokens }
}

struct UsageApp: Codable, Identifiable, Hashable {
    let app: String
    let inputTokens: Int
    let outputTokens: Int
    let cachedInputTokens: Int
    let cacheWriteInputTokens: Int
    let reasoningOutputTokens: Int
    let totalTokens: Int
    let requests: Int

    var id: String { app }
}

struct UsageSourceStatus: Codable, Identifiable, Hashable {
    let adapter: String
    let available: Bool

    var id: String { adapter }
}

struct UsageSummary: Codable {
    let version: Int
    let updatedAt: Int?
    let today: UsageTotalsWithDate
    let week: UsageWeek
    let daily: [UsageDay]
    let apps: [UsageApp]
    let sources: [UsageSourceStatus]
}

struct UsageTotalsWithDate: Codable {
    let date: String
    let inputTokens: Int
    let outputTokens: Int
    let cachedInputTokens: Int
    let cacheWriteInputTokens: Int
    let reasoningOutputTokens: Int
    let totalTokens: Int
    let requests: Int

    var inputOutputTokens: Int { inputTokens + outputTokens }
}

struct UsageWeek: Codable {
    let startDate: String
    let endDate: String
    let inputTokens: Int
    let outputTokens: Int
    let cachedInputTokens: Int
    let cacheWriteInputTokens: Int
    let reasoningOutputTokens: Int
    let totalTokens: Int
    let requests: Int

    var inputOutputTokens: Int { inputTokens + outputTokens }
}

struct PopoverLayout: Equatable {
    static let alertSlotHeight: CGFloat = 54
    static let alertBannerHeight: CGFloat = 44
    static let footerHeight: CGFloat = 34

    let width: CGFloat
    let height: CGFloat
    let columns: Int
    let ringDiameter: CGFloat
    let scrolls: Bool
    let reservesAlertSpace: Bool

    static func make(
        rings: [Ring],
        visibleScreenSize: CGSize,
        hasAlerts: Bool = false
    ) -> PopoverLayout {
        make(
            ringCount: rings.count,
            visibleScreenSize: visibleScreenSize,
            hasAlerts: hasAlerts,
            showsRingVisualization: !RingPresentation.quotaRings(rings).isEmpty
        )
    }

    static func make(
        ringCount: Int,
        visibleScreenSize: CGSize,
        hasAlerts: Bool = false,
        showsRingVisualization: Bool = true
    ) -> PopoverLayout {
        let count = max(ringCount, 0)
        let columns = count >= 6 ? 2 : 1
        let width = min(columns == 2 ? 620 : 380, max(320, visibleScreenSize.width - 32))
        // NSPopover adds roughly 26 pt for its arrow and outer frame; reserve
        // 28 pt so the complete popup (not just SwiftUI content) stays within
        // half of the current screen's visible height.
        let maxHeight = max(1, floor(visibleScreenSize.height * 0.5) - 28)
        let rowCount = max(1, Int(ceil(Double(max(count, 1)) / Double(columns))))
        let fixedHeight: CGFloat = 88 + footerHeight + (hasAlerts ? alertSlotHeight : 0)
        let rowHeight: CGFloat = 44
        let preferredRing: CGFloat = count <= 3 ? 150 : (count <= 5 ? 110 : 118)
        let availableRing = maxHeight - fixedHeight - CGFloat(rowCount) * rowHeight
        let ringDiameter = showsRingVisualization ? min(preferredRing, max(64, availableRing)) : 0
        let desiredHeight = fixedHeight + ringDiameter + CGFloat(rowCount) * rowHeight

        return PopoverLayout(
            width: width,
            height: min(desiredHeight, maxHeight),
            columns: columns,
            ringDiameter: ringDiameter,
            scrolls: desiredHeight > maxHeight,
            reservesAlertSpace: hasAlerts
        )
    }
}

struct PopoverAlertLayoutState: Equatable {
    private(set) var reservesAlertSpace: Bool

    init(hasAlerts: Bool) {
        reservesAlertSpace = hasAlerts
    }

    mutating func observe(hasAlerts: Bool) {
        if hasAlerts { reservesAlertSpace = true }
    }
}

enum RingPresentation {
    static func quotaRings(_ rings: [Ring]) -> [Ring] {
        rings.filter(\.hasQuotaValue)
    }
}

struct MenuBarLayout: Equatable {
    let barWidth: CGFloat
    let barHeight: CGFloat
    let gap: CGFloat
    let top: CGFloat

    static func make(
        ringCount: Int,
        imageWidth: CGFloat = 24,
        imageHeight: CGFloat = 18
    ) -> MenuBarLayout {
        let count = max(ringCount, 1)
        let horizontalInset: CGFloat = 1
        let verticalInset: CGFloat = 1
        let gap: CGFloat = count <= 5 ? 1 : 0.5
        let availableHeight = imageHeight - verticalInset * 2 - CGFloat(count - 1) * gap
        let barHeight = max(1, min(3, availableHeight / CGFloat(count)))
        let contentHeight = CGFloat(count) * barHeight + CGFloat(count - 1) * gap
        return MenuBarLayout(
            barWidth: imageWidth - horizontalInset * 2,
            barHeight: barHeight,
            gap: gap,
            top: (imageHeight - contentHeight) / 2
        )
    }
}

enum Palette {
    static func color(_ name: String?) -> Color {
        switch name {
        case "blue": return .blue
        case "indigo": return .indigo
        case "green": return .green
        case "orange": return .orange
        case "red": return .red
        case "purple": return .purple
        case "teal": return .teal
        case "gray": return .secondary
        default: return .blue
        }
    }
}

extension Ring {
    var fillPercent: Int { usedPercent ?? 0 }
    var hasQuotaValue: Bool { usedPercent != nil }

    var usageText: String {
        if status == "not_connected" { return "Not connected" }
        if status == "quota_unavailable" { return "Unavailable" }
        if status == "quota_unsupported" { return "Not supported" }
        guard let usedValue, let totalValue else {
            return "Quota unavailable"
        }
        return "\(formatValue(usedValue)) / \(formatValue(totalValue))" + usagePercentSuffix
    }

    /// Percent appended to "used / total" so credit quotas and prepaid balances
    /// always surface a ratio, even when the detail line shows a reset countdown.
    private var usagePercentSuffix: String {
        guard let usedPercent, valueUnit != "percent" else { return "" }
        return " · \(usedPercent)%"
    }

    private func formatValue(_ value: Double) -> String {
        if valueUnit == "tokens" {
            return formatHoverTokenCount(Int(value.rounded()))
        }
        let number = value.rounded() == value
            ? String(format: "%.0f", value)
            : String(format: "%.2f", value)
        switch valueUnit {
        case "USD": return "$\(number)"
        case "CNY": return "¥\(number)"
        case "percent": return "\(number)%"
        default: return number
        }
    }

    /// Reset countdown shared by the bar-row detail line and hover tooltips.
    var resetText: String? {
        guard let reset = resetsAt else { return nil }
        let s = Double(reset) - Date().timeIntervalSince1970
        if s <= 0 { return "quota window ended" }
        let m = Int(s / 60)
        if m >= 1440 { return "resets in \(m / 1440)d" }
        if m >= 60 { return "resets in \(m / 60)h \(m % 60)m" }
        return "resets in \(m)m"
    }

    /// Multi-line tooltip shown when hovering a ring arc or bar row.
    var hoverText: String {
        var lines = [label, usageText]
        if let usedPercent { lines.append("\(usedPercent)% used") }
        if let remaining {
            let number = remaining.rounded() == remaining
                ? String(format: "%.0f", remaining)
                : String(format: "%.2f", remaining)
            let unit = currency ?? valueUnit ?? ""
            lines.append("remaining \(number) \(unit)".trimmingCharacters(in: .whitespaces))
        }
        if let resetText { lines.append(resetText) }
        if let statusDetail { lines.append(statusDetail) }
        return lines.joined(separator: "\n")
    }

}
