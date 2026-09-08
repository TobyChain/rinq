import Foundation
import SwiftUI

struct TRStatus: Codable {
    var version: Int?
    var updatedAt: Int?
    var rings: [TRRing]

    static let sample: TRStatus = {
        guard let url = Bundle.main.url(forResource: "sample_status", withExtension: "json"),
              let data = try? Data(contentsOf: url),
              let status = try? JSONDecoder().decode(TRStatus.self, from: data) else {
            return TRStatus(rings: [])
        }
        return status
    }()
}

struct TRRing: Codable, Identifiable {
    var id: String
    var label: String
    var vendor: String?
    var kind: String?
    var usedPercent: Int?
    var remainingPercent: Int?
    var remaining: Double?
    var currency: String?
    var resetsAt: Int?
    var windowMins: Int?
    var accent: String?
    var spentUsd: Double?
    var budgetUsd: Double?
    var status: String?
}

enum TRPalette {
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

/// A vendor quota source the app can fetch on its own (no Mac required).
enum TRVendor: String, CaseIterable, Identifiable {
    case chatgpt, minimax, deepseek, moonshot, zhipu, openai
    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .chatgpt: return "ChatGPT / Codex"
        case .minimax: return "MiniMax"
        case .deepseek: return "DeepSeek"
        case .moonshot: return "Kimi (Moonshot)"
        case .zhipu: return "GLM (Zhipu)"
        case .openai: return "OpenAI API spend"
        }
    }

    var keyLabel: String {
        switch self {
        case .chatgpt: return "ChatGPT access token (experimental)"
        case .openai: return "OpenAI Admin key"
        default: return "\(displayName) API key"
        }
    }
}
