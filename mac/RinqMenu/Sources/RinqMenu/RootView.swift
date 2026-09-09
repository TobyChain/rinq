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
    @State private var tab: RinqTab = .rings

    private var layout: PopoverLayout {
        PopoverLayout.make(
            ringCount: store.status?.rings.count ?? 0,
            visibleScreenSize: visibleScreenSize,
            hasAlerts: !store.alerts.isEmpty
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

            if !store.alerts.isEmpty {
                AlertBanner(alerts: store.alerts)
                    .padding(.horizontal, 12)
                    .padding(.top, 10)
            }

            Group {
                switch tab {
                case .rings: DashboardView(store: store, layout: layout)
                case .usage: UsageView(store: store)
                case .providers: SettingsView(store: store)
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .frame(width: layout.width, height: layout.height)
        .background(Color(NSColor.windowBackgroundColor))
        .onAppear { onLayoutChange(layout) }
        .onChange(of: layout) { onLayoutChange($0) }
    }
}
