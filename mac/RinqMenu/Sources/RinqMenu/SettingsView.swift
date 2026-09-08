import SwiftUI

struct DashboardView: View {
    @ObservedObject var store: Store

    var body: some View {
        ScrollView {
            VStack(spacing: 18) {
                RingsView(rings: store.status?.rings ?? [])
                    .padding(.top, 6)
                VStack(spacing: 14) {
                    ForEach(store.status?.rings ?? []) { ring in
                        BarRow(ring: ring)
                    }
                }
                .padding(.horizontal)
                Text(updated)
                    .font(.system(size: 10))
                    .foregroundStyle(.secondary)
            }
            .padding(.bottom, 16)
        }
        .frame(width: 320)
    }

    private var updated: String {
        guard let t = store.status?.updatedAt else { return "waiting for rinq daemon…" }
        let f = DateFormatter()
        f.dateFormat = "HH:mm"
        return "updated \(f.string(from: Date(timeIntervalSince1970: TimeInterval(t))))"
    }
}

struct SettingsView: View {
    @ObservedObject var store: Store
    @State private var orderExpanded = false

    var body: some View {
        Form {
            Section("Providers") {
                if let vendors = store.settings?.vendors {
                    ForEach(vendors) { v in
                        ProviderRow(store: store, vendor: v)
                    }
                } else {
                    Text("Connecting to rinq daemon…").foregroundStyle(.secondary)
                }
            }
            Section("Ring order") {
                if let rings = store.status?.rings, !rings.isEmpty {
                    Toggle("Customize", isOn: $orderExpanded)
                    if orderExpanded {
                        ForEach(rings) { ring in
                            HStack {
                                Circle().fill(Palette.color(ring.accent)).frame(width: 9, height: 9)
                                Text(ring.label).font(.system(size: 12))
                                Spacer()
                            }
                        }
                        Text("Drag in the macOS app / web dashboard to reorder; order is saved to the daemon.")
                            .font(.system(size: 10)).foregroundStyle(.secondary)
                    }
                } else {
                    Text("No active rings — add a provider key.").font(.system(size: 11))
                        .foregroundStyle(.secondary)
                }
            }
        }
        .formStyle(.grouped)
        .frame(width: 340, height: 420)
    }
}

struct ProviderRow: View {
    @ObservedObject var store: Store
    let vendor: VendorInfo
    @State private var showKey = false
    @State private var expanded = false

    var body: some View {
        DisclosureGroup(isExpanded: $expanded) {
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    SecureField("API key", text: Binding(
                        get: { store.keyDraft(vendor.id) },
                        set: { store.setDraft(vendor.id, $0) }))
                        .textFieldStyle(.roundedBorder)
                        .font(.system(size: 11))
                    Button("Save") { Task { await store.saveKey(vendor.id) } }
                        .controlSize(.small)
                }
                HStack(spacing: 8) {
                    Label(vendor.hasCredential ? "credential found" : "no credential",
                          systemImage: vendor.hasCredential ? "checkmark.circle.fill" : "circle")
                        .foregroundStyle(vendor.hasCredential ? .green : .secondary)
                        .font(.system(size: 10))
                    Spacer()
                    if vendor.hasKeySet {
                        Button("Clear key", role: .destructive) { Task { await store.clearKey(vendor.id) } }
                            .controlSize(.small)
                    }
                }
                Text(vendor.id == "codex"
                     ? "Reads the Codex ChatGPT login automatically (no key needed)."
                     : "Paste the API key from this provider's console. Stored locally in ~/.rinq/config.json, sent only to this vendor.")
                    .font(.system(size: 10)).foregroundStyle(.secondary)
            }
            .padding(.vertical, 4)
        } label: {
            HStack {
                Circle().fill(Palette.color(vendor.accent)).frame(width: 10, height: 10)
                Text(vendor.label).font(.system(size: 12, weight: .medium))
                Spacer()
                if vendor.hasCredential {
                    Image(systemName: "bolt.fill").foregroundStyle(.green).font(.system(size: 10))
                }
                Toggle("", isOn: Binding(
                    get: { vendor.enabled },
                    set: { _ in Task { await store.toggle(vendor) } }))
                    .labelsHidden()
                    .toggleStyle(.switch)
                    .controlSize(.small)
            }
        }
    }
}
