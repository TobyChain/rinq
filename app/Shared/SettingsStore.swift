import Foundation
import SwiftUI

/// Shared settings for the app and its widgets.
///
/// Storage uses an App Group container so the widget extension can read keys
/// entered in the app. When running in contexts without the App Group
/// capability, it falls back to the standard defaults. Keys stay on device and
/// are sent only to the matching vendor endpoint.
final class TRSettings: ObservableObject {
    static let appGroup = "group.com.tobychain.rinq"
    static let shared = TRSettings()

    private let defaults: UserDefaults

    init() {
        defaults = UserDefaults(suiteName: Self.appGroup) ?? .standard
    }

    func key(_ vendor: TRVendor) -> String {
        (defaults.string(forKey: "key.\(vendor.rawValue)") ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
    }

    func setKey(_ vendor: TRVendor, _ value: String) {
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.isEmpty {
            defaults.removeObject(forKey: "key.\(vendor.rawValue)")
        } else {
            defaults.set(trimmed, forKey: "key.\(vendor.rawValue)")
        }
        objectWillChange.send()
    }

    var chatGPTAccountId: String {
        (defaults.string(forKey: "chatgpt.accountId") ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
    }

    func setChatGPTAccountId(_ value: String) {
        let v = value.trimmingCharacters(in: .whitespacesAndNewlines)
        v.isEmpty ? defaults.removeObject(forKey: "chatgpt.accountId") : defaults.set(v, forKey: "chatgpt.accountId")
        objectWillChange.send()
    }

    var enabledVendors: Set<TRVendor> {
        get {
            let raw = defaults.array(forKey: "enabledVendors") as? [String]
                ?? TRVendor.allCases.map(\.rawValue)
            return Set(raw.compactMap(TRVendor.init(rawValue:)))
        }
        set {
            defaults.set(newValue.map(\.rawValue), forKey: "enabledVendors")
            objectWillChange.send()
        }
    }
}
