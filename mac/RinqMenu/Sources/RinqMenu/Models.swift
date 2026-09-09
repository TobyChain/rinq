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
    let accent: String?
    let spentUsd: Double?
    let budgetUsd: Double?
    let usedValue: Double?
    let totalValue: Double?
    let valueUnit: String?
    let status: String?
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

struct SettingsInfo: Codable {
    let ringOrder: [String]
    let vendors: [VendorInfo]
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
    let width: CGFloat
    let height: CGFloat
    let columns: Int
    let ringDiameter: CGFloat
    let scrolls: Bool

    static func make(ringCount: Int, visibleScreenSize: CGSize) -> PopoverLayout {
        let count = max(ringCount, 0)
        let columns = count >= 6 ? 2 : 1
        let width = min(columns == 2 ? 620 : 380, max(320, visibleScreenSize.width - 32))
        // NSPopover adds roughly 26 pt for its arrow and outer frame; reserve
        // 28 pt so the complete popup (not just SwiftUI content) stays within
        // half of the current screen's visible height.
        let maxHeight = max(1, floor(visibleScreenSize.height * 0.5) - 28)
        let rowCount = max(1, Int(ceil(Double(max(count, 1)) / Double(columns))))
        let fixedHeight: CGFloat = 88
        let rowHeight: CGFloat = 44
        let preferredRing: CGFloat = count <= 3 ? 150 : (count <= 5 ? 110 : 118)
        let availableRing = maxHeight - fixedHeight - CGFloat(rowCount) * rowHeight
        let ringDiameter = min(preferredRing, max(64, availableRing))
        let desiredHeight = fixedHeight + ringDiameter + CGFloat(rowCount) * rowHeight

        return PopoverLayout(
            width: width,
            height: min(desiredHeight, maxHeight),
            columns: columns,
            ringDiameter: ringDiameter,
            scrolls: desiredHeight > maxHeight
        )
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
        default: return .blue
        }
    }
}

extension Ring {
    var fillPercent: Int { usedPercent ?? 0 }

    var usageText: String {
        guard let usedValue, let totalValue else {
            return "\(fillPercent)% / 100%"
        }
        return "\(formatValue(usedValue)) / \(formatValue(totalValue))"
    }

    private func formatValue(_ value: Double) -> String {
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
}
