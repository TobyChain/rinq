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
    let status: String?
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
