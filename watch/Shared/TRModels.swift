import Foundation
import SwiftUI

struct TRStatus: Codable {
    var version: Int?
    var updatedAt: Int?
    var rings: [TRRing]
    var agents: TRAgents?
    var focus: TRFocus?

    static let sample: TRStatus = {
        guard let url = Bundle.main.url(forResource: "sample_status", withExtension: "json"),
              let data = try? Data(contentsOf: url),
              let status = try? JSONDecoder().decode(TRStatus.self, from: data) else {
            return TRStatus(rings: [], agents: nil, focus: nil)
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

struct TRAgents: Codable {
    var running: Int?
    var waiting: Int?
    var doneToday: Int?
    var failedToday: Int?
    var lastEvent: TREvent?
}

struct TREvent: Codable {
    var state: String?
    var title: String?
    var at: Int?
}

struct TRFocus: Codable {
    var mode: String?
    var remainingMins: Int?
    var breakEveryMins: Int?
}

enum TRStatusLoader {
    static func remote() async -> TRStatus? {
        guard let url = endpoint else { return nil }
        do {
            let (data, response) = try await URLSession.shared.data(from: url)
            guard let http = response as? HTTPURLResponse, http.statusCode == 200 else { return nil }
            return try JSONDecoder().decode(TRStatus.self, from: data)
        } catch {
            return nil
        }
    }

    static var endpoint: URL? {
        let s = UserDefaults.standard.string(forKey: "statusURL")?.trimmingCharacters(in: .whitespaces) ?? ""
        return s.isEmpty ? nil : URL(string: s)
    }
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
