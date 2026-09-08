import SwiftUI

@main
struct RinqIOSApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}

struct ContentView: View {
    @ObservedObject private var settings = TRSettings.shared
    @State private var status: TRStatus?
    @State private var loading = false

    var shownRings: [TRRing] {
        let rings = status?.rings ?? []
        return rings.isEmpty ? TRStatus.sample.rings : rings
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 20) {
                    RingStackView(rings: shownRings, outerDiameter: 180)
                        .padding(.top, 8)

                    VStack(spacing: 14) {
                        ForEach(shownRings) { ring in
                            BarRow(ring: ring)
                        }
                    }
                    .padding(.horizontal)

                    Text(updatedText)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                .padding(.bottom, 24)
            }
            .navigationTitle("Rinq")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        Task { await refresh() }
                    } label: {
                        Image(systemName: "arrow.clockwise")
                    }
                    .disabled(loading)
                }
                ToolbarItem(placement: .topBarLeading) {
                    NavigationLink {
                        SettingsView()
                    } label: {
                        Image(systemName: "key.horizontal")
                    }
                }
            }
            .task { await refreshIfNeeded() }
        }
    }

    private var updatedText: String {
        guard let t = status?.updatedAt, !(status?.rings.isEmpty ?? true) else {
            return "sample data — open settings (key icon) and paste keys"
        }
        let f = DateFormatter()
        f.dateFormat = "HH:mm"
        return "updated \(f.string(from: Date(timeIntervalSince1970: TimeInterval(t))))"
    }

    private func refreshIfNeeded() async {
        if let cached = TRStatusCache.shared.cached {
            status = cached
        }
        await refresh()
    }

    private func refresh() async {
        loading = true
        defer { loading = false }
        status = await TRProviders.fetchAll(using: settings)
    }
}

struct SettingsView: View {
    @ObservedObject private var settings = TRSettings.shared
    @State private var keys: [TRVendor: String] = [:]
    @State private var accountId = ""

    var body: some View {
        Form {
            Section {
                Text("Enter a provider key to show its quota. Keys stay on this device in the App Group container and are sent only to that provider.")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }
            ForEach(TRVendor.allCases) { vendor in
                Section {
                    SecureField(vendor.keyLabel, text: binding(for: vendor))
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    Toggle("Enabled", isOn: enabledBinding(vendor))
                    if vendor == .chatgpt {
                        TextField("ChatGPT account id (optional)", text: $accountId)
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()
                            .onChange(of: accountId) { _, v in settings.setChatGPTAccountId(v) }
                    }
                } header: {
                    Text(vendor.displayName)
                } footer: {
                    if vendor == .chatgpt {
                        Text("Experimental. Uses an unofficial ChatGPT endpoint with your own account; not App-Store eligible, may break. See README.")
                    }
                }
            }
        }
        .navigationTitle("Providers")
        .onAppear {
            for v in TRVendor.allCases { keys[v] = settings.key(v) }
            accountId = settings.chatGPTAccountId
        }
    }

    private func binding(for vendor: TRVendor) -> Binding<String> {
        Binding(
            get: { keys[vendor] ?? "" },
            set: { newValue in
                keys[vendor] = newValue
                settings.setKey(vendor, newValue)
            }
        )
    }

    private func enabledBinding(_ vendor: TRVendor) -> Binding<Bool> {
        Binding(
            get: { settings.enabledVendors.contains(vendor) },
            set: { on in
                var set = settings.enabledVendors
                if on { set.insert(vendor) } else { set.remove(vendor) }
                settings.enabledVendors = set
            }
        )
    }
}
