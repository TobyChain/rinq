import SwiftUI

struct DashboardView: View {
    @ObservedObject var store: Store
    let layout: PopoverLayout

    var body: some View {
        Group {
            if layout.scrolls {
                ScrollView { content }
            } else {
                content
            }
        }
    }

    private var content: some View {
        VStack(spacing: 8) {
            RingsView(rings: store.status?.rings ?? [], diameter: layout.ringDiameter)
                .padding(.top, 4)

            LazyVGrid(
                columns: Array(
                    repeating: GridItem(.flexible(), spacing: 12),
                    count: layout.columns
                ),
                spacing: 8
            ) {
                ForEach(store.status?.rings ?? []) { ring in
                    BarRow(ring: ring, compact: layout.columns == 2)
                }
            }
            .padding(.horizontal, 14)

            if (store.status?.rings ?? []).isEmpty {
                Text("No active rings. Add a provider in the Providers tab.")
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
            }

            Text(updated)
                .font(.system(size: 10))
                .foregroundStyle(.secondary)
                .padding(.bottom, 6)
        }
        .frame(maxWidth: .infinity)
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

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                GroupBox("Providers") {
                    VStack(spacing: 0) {
                if let vendors = store.settings?.vendors {
                    ForEach(vendors) { v in
                        ProviderRow(store: store, vendor: v)
                            .padding(.vertical, 5)
                        if v.id != vendors.last?.id { Divider() }
                    }
                } else {
                            Text("Connecting to rinq daemon…")
                                .foregroundStyle(.secondary)
                                .padding(8)
                        }
                    }
                }

                GroupBox("Ring order") {
                    if let rings = store.status?.rings, !rings.isEmpty {
                        RingOrderView(store: store, rings: rings)
                            .padding(.vertical, 4)
                    } else {
                        Text("No active rings — add a provider key.")
                            .font(.system(size: 11))
                            .foregroundStyle(.secondary)
                            .padding(8)
                    }
                }
            }
            .padding(12)
        }
        .frame(maxWidth: .infinity)
    }
}

struct ProviderRow: View {
    @ObservedObject var store: Store
    let vendor: VendorInfo
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
