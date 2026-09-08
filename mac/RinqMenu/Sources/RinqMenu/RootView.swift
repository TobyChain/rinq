import SwiftUI

enum RinqTab: String, CaseIterable {
    case rings, providers
    var title: String { self == .rings ? "Rings" : "Providers" }
    var icon: String { self == .rings ? "circle.hexagongrid" : "slider.horizontal.3" }
}

/// The single Rinq interface shown in the menu-bar popover.
struct RootView: View {
    @ObservedObject var store: Store
    @State private var tab: RinqTab = .rings

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

            Group {
                switch tab {
                case .rings: DashboardView(store: store)
                case .providers: SettingsView(store: store)
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .background(Color(NSColor.windowBackgroundColor))
    }
}
