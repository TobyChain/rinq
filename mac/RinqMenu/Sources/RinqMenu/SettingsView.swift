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
        let allRings = store.status?.rings ?? []
        let quotaRings = RingPresentation.quotaRings(allRings)
        return VStack(spacing: 8) {
            if !quotaRings.isEmpty {
                RingsView(
                    rings: quotaRings,
                    alerts: store.alerts,
                    diameter: layout.ringDiameter
                )
                    .padding(.top, 4)
            }

            LazyVGrid(
                columns: Array(
                    repeating: GridItem(.flexible(), spacing: 12),
                    count: layout.columns
                ),
                spacing: 8
            ) {
                ForEach(allRings) { ring in
                    BarRow(
                        ring: ring,
                        alerts: store.alerts,
                        compact: layout.columns == 2
                    )
                }
            }
            .padding(.horizontal, 14)

            if allRings.isEmpty {
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

    private var detectedIntegrations: [IntegrationInfo] {
        (store.settings?.integrations ?? []).filter {
            $0.installed || $0.configured || $0.running || $0.usageAvailable
        }
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                GroupBox("Local coding IDEs") {
                    VStack(alignment: .leading, spacing: 8) {
                        if !detectedIntegrations.isEmpty {
                            ForEach(detectedIntegrations) { integration in
                                IntegrationRow(store: store, integration: integration)
                                if integration.id != detectedIntegrations.last?.id { Divider() }
                            }
                        } else {
                            Text("No supported coding IDE detected.")
                                .font(.system(size: 11))
                                .foregroundStyle(.secondary)
                        }
                    }
                    .padding(.vertical, 4)
                }

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

private struct IntegrationRow: View {
    @ObservedObject var store: Store
    let integration: IntegrationInfo

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Circle()
                    .fill(integration.installed ? (integration.running ? Color.green : Color.orange) : (integration.configured ? Color.blue : Color.secondary))
                    .frame(width: 8, height: 8)
                Text(integration.label)
                    .font(.system(size: 12, weight: .medium))
                if let version = integration.version {
                    Text("v\(version)")
                        .font(.system(size: 9, design: .monospaced))
                        .foregroundStyle(.secondary)
                }
                Spacer()
                if integration.installed || integration.configured {
                    Button(integration.authState == "connected" ? "Open account" : "Connect account") {
                        Task { await store.connect(integration) }
                    }
                    .controlSize(.small)
                }
            }
            HStack(spacing: 8) {
                Text(integration.installed ? (integration.running ? "running" : "installed") : (integration.configured ? "configured" : "not installed"))
                Text("login: \(integration.authState)")
                Text("plan: \(integration.planState)")
                if integration.usageAvailable { Text("usage tracked") }
            }
            .font(.system(size: 9))
            .foregroundStyle(.secondary)
            if integration.authState == "connected" && integration.quotaState != "available" {
                Text("Account detected. This vendor does not expose a verified quota value to Rinq yet.")
                    .font(.system(size: 9))
                    .foregroundStyle(.secondary)
            }
            if let quotaSupport = integration.quotaSupport, quotaSupport != "verified" {
                Text("quota support: \(quotaSupport)")
                    .font(.system(size: 9))
                    .foregroundStyle(.tertiary)
            }
        }
        .padding(.vertical, 4)
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
