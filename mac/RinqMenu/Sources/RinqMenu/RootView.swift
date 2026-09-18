import AppKit
import SwiftUI

enum RinqTab: String, CaseIterable {
    case rings, usage, providers

    var title: String {
        switch self {
        case .rings: return "Rings"
        case .usage: return "Usage"
        case .providers: return "Providers"
        }
    }

    var icon: String {
        switch self {
        case .rings: return "circle.hexagongrid"
        case .usage: return "chart.bar.xaxis"
        case .providers: return "slider.horizontal.3"
        }
    }
}

/// The single Rinq interface shown in the menu-bar popover.
struct RootView: View {
    @ObservedObject var store: Store
    let visibleScreenSize: CGSize
    let onLayoutChange: (PopoverLayout) -> Void
    let onAlertsDismissed: () -> Void
    @State private var tab: RinqTab = .rings
    @State private var alertLayoutState: PopoverAlertLayoutState

    init(
        store: Store,
        visibleScreenSize: CGSize,
        onLayoutChange: @escaping (PopoverLayout) -> Void,
        onAlertsDismissed: @escaping () -> Void
    ) {
        self.store = store
        self.visibleScreenSize = visibleScreenSize
        self.onLayoutChange = onLayoutChange
        self.onAlertsDismissed = onAlertsDismissed
        _alertLayoutState = State(initialValue: PopoverAlertLayoutState(hasAlerts: !store.alerts.isEmpty))
    }

    private var layout: PopoverLayout {
        let rings = store.status?.rings ?? []
        return PopoverLayout.make(
            rings: rings,
            visibleScreenSize: visibleScreenSize,
            hasAlerts: alertLayoutState.reservesAlertSpace
        )
    }

    var body: some View {
        VStack(spacing: 0) {
            Picker("", selection: $tab) {
                ForEach(RinqTab.allCases, id: \.self) { t in
                    Text(t.title).tag(t)
                }
            }
            .pickerStyle(.segmented)
            .labelsHidden()
            .padding(.horizontal, 16)
            .padding(.top, 14)
            .padding(.bottom, 10)

            Divider()

            if alertLayoutState.reservesAlertSpace {
                ZStack {
                    if !store.alerts.isEmpty {
                        AlertBanner(alerts: store.alerts)
                            .help("Click anywhere in this window to dismiss until the quota condition clears")
                    }
                }
                .frame(height: PopoverLayout.alertBannerHeight)
                .padding(.horizontal, 12)
                .padding(.top, PopoverLayout.alertSlotHeight - PopoverLayout.alertBannerHeight)
            }

            Group {
                switch tab {
                case .rings: DashboardView(store: store, layout: layout)
                case .usage: UsageView(store: store)
                case .providers: SettingsView(store: store)
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)

            Divider()

            PopoverFooter()
        }
        .frame(width: layout.width, height: layout.height)
        .background(Color(NSColor.windowBackgroundColor))
        .contentShape(Rectangle())
        .simultaneousGesture(
            TapGesture().onEnded { dismissActiveAlerts() }
        )
        .accessibilityAction(named: Text("Dismiss quota alert")) { dismissActiveAlerts() }
        .onAppear { onLayoutChange(layout) }
        .onChange(of: layout) { onLayoutChange($0) }
        .onChange(of: !store.alerts.isEmpty) { hasAlerts in
            alertLayoutState.observe(hasAlerts: hasAlerts)
        }
    }

    private func dismissActiveAlerts() {
        var dismissed = false
        withAnimation(nil) { dismissed = store.dismissAlerts() }
        if dismissed { onAlertsDismissed() }
    }
}

/// A persistent bottom bar. Provides an explicit way to quit the menu-bar app,
/// which otherwise has no window chrome or app menu.
struct PopoverFooter: View {
    var body: some View {
        HStack(spacing: 0) {
            Spacer(minLength: 0)
            Button {
                NSApplication.shared.terminate(nil)
            } label: {
                Label("Quit Rinq", systemImage: "power")
                    .font(.system(size: 11, weight: .medium))
                    .labelStyle(.titleAndIcon)
            }
            .buttonStyle(.plain)
            .foregroundStyle(.secondary)
            .help("Quit the Rinq menu-bar app")
            .accessibilityLabel("Quit Rinq")
        }
        .padding(.horizontal, 14)
        .frame(height: PopoverLayout.footerHeight)
    }
}
