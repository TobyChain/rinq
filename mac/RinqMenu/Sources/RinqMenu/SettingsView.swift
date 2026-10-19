import SwiftUI

struct DashboardView: View {
    @ObservedObject var store: Store
    let layout: PopoverLayout

    var body: some View {
        Group {
            if layout.scrolls {
                ScrollView { content }
            } else {
                // Center the dashboard vertically inside the popover's
                // minimum height so a sparse window (a single source, or the
                // empty state) reads as a quiet dashboard, not a stub.
                VStack(spacing: 0) {
                    Spacer(minLength: 0)
                    content
                    Spacer(minLength: 0)
                }
            }
        }
    }

    private var content: some View {
        let allRings = store.status?.rings ?? []
        return VStack(spacing: 0) {
            if let snapshot = store.sessions, snapshot.sessions.contains(where: { $0.isOpen == true }) {
                AgentSessionsPanel(snapshot: snapshot)
            }

            if allRings.isEmpty {
                Text("No active rings. Add a provider in the Providers tab.")
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                    .frame(maxWidth: .infinity)
                    .frame(height: PopoverLayout.emptyRowsHeight)
                    .padding(.horizontal, 14)
            } else {
                VStack(spacing: 0) {
                    ForEach(allRings) { ring in
                        ProviderQuotaRow(
                            ring: ring,
                            alerts: store.alerts
                        )
                    }
                }
                .padding(.horizontal, 12)
                .padding(.top, 8)
            }

            Spacer(minLength: 0)

            Text(updated)
                .font(.system(size: 10))
                .foregroundStyle(.secondary)
                .padding(.top, 4)
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
        (store.settings?.integrations ?? []).filter(\.isListed)
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                GroupBox {
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
                } label: {
                    HStack {
                        Text("Local coding IDEs")
                        Spacer()
                        Button {
                            Task { await store.refreshIntegrations() }
                        } label: {
                            Label("Refresh", systemImage: "arrow.clockwise")
                        }
                        .controlSize(.small)
                        .help("Scan this Mac again for local coding IDEs")
                    }
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
            HStack(spacing: 8) {
                Circle().fill(dotColor).frame(width: 8, height: 8)
                Text(integration.label)
                    .font(.system(size: 12, weight: .medium))
                if let version = integration.version {
                    Text("v\(version)")
                        .font(.system(size: 9, design: .monospaced))
                        .foregroundStyle(.secondary)
                }
                Spacer(minLength: 6)
                Toggle("", isOn: monitored)
                    .labelsHidden()
                    .toggleStyle(.switch)
                    .tint(.green)
                    .controlSize(.small)
                    .help(integration.monitored ? "Monitoring is on" : "Monitoring is off")
            }
            if integration.monitored {
                detailLines
            }
        }
        .padding(.vertical, 4)
    }

    /// A cancelled IDE is not probed, so only its identity row is shown.
    /// This section manages local usage monitoring only; account, plan, and
    /// quota state belong to the Providers section below.
    @ViewBuilder
    private var detailLines: some View {
        if integration.usageAvailable {
            Text("usage tracked")
                .font(.system(size: 9))
                .foregroundStyle(.secondary)
                .help("Rinq indexes this IDE's structured local usage logs.")
        }
    }

    private var dotColor: Color {
        guard integration.monitored else { return .secondary }
        if integration.installed {
            return integration.running ? .green : .orange
        }
        return integration.configured ? .blue : .secondary
    }

    private var monitored: Binding<Bool> {
        Binding(
            get: { integration.monitored },
            set: { on in Task { await store.setIntegrationMonitored(integration.id, on) } }
        )
    }
}

struct ProviderRow: View {
    @ObservedObject var store: Store
    let vendor: VendorInfo
    @State private var expanded = false

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            header
            if expanded { details }
        }
    }

    /// The whole bar toggles the details, so expanding does not depend on
    /// hitting the disclosure triangle.
    private var header: some View {
        HStack(spacing: 8) {
            HStack(spacing: 6) {
                Circle().fill(Palette.color(vendor.accent)).frame(width: 10, height: 10)
                Text(vendor.label).font(.system(size: 12, weight: .medium))
                Image(systemName: expanded ? "chevron.down" : "chevron.right")
                    .font(.system(size: 9, weight: .semibold))
                    .foregroundStyle(.tertiary)
                Spacer(minLength: 6)
            }
            .contentShape(Rectangle())
            .onTapGesture { expanded.toggle() }

            Toggle("", isOn: tracking)
                .labelsHidden()
                .toggleStyle(.switch)
                .tint(.green)
                .controlSize(.small)
                .disabled(!vendor.hasCredential)
                .help(trackingHelp)
        }
    }

    private var details: some View {
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
            if vendor.hasKeySet {
                HStack {
                    Button("Clear key", role: .destructive) { Task { await store.clearKey(vendor.id) } }
                        .controlSize(.small)
                    Spacer()
                }
            }
            Text(hint)
                .font(.system(size: 10)).foregroundStyle(.secondary)
        }
        .padding(.vertical, 4)
    }

    private var tracking: Binding<Bool> {
        Binding(
            get: { vendor.tracking },
            set: { on in Task { await store.setTracking(vendor.id, on) } }
        )
    }

    private var trackingHelp: String {
        if !vendor.hasCredential { return "Add a credential below to track this provider" }
        return vendor.tracking ? "Quota tracking is on" : "Quota tracking is cancelled"
    }

    private var hint: String {
        if vendor.trackingCancelled {
            return "Quota tracking is cancelled. Rinq keeps the credential but stops fetching this vendor and hides its rings."
        }
        if vendor.id == "codex" {
            return "Reads the Codex ChatGPT login automatically (no key needed)."
        }
        return "Paste the API key from this provider's console. Stored locally in ~/.rinq/config.json, sent only to this vendor."
    }
}
