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
    static func moving(_ rings: [Ring], draggedID: String, before targetID: String) -> [Ring] {
        guard draggedID != targetID,
              let source = rings.firstIndex(where: { $0.id == draggedID }),
              let target = rings.firstIndex(where: { $0.id == targetID }) else { return rings }

        var result = rings
        let moved = result.remove(at: source)
        // Removing an item before the target shifts the target one slot left.
        // Insert at the original target index to place it after that row; for
        // upward moves, insert directly at the target index.
        let insertion = source < target ? min(target, result.count) : target
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
