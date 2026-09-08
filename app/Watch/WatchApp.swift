import SwiftUI

@main
struct RinqWatchApp: App {
    var body: some Scene {
        WindowGroup {
            WatchContentView()
        }
    }
}

struct WatchContentView: View {
    @State private var status: TRStatus = .sample

    var body: some View {
        TabView {
            OverviewPage(rings: status.rings)
            ForEach(vendors, id: \.self) { vendor in
                VendorPage(rings: rings(for: vendor), vendor: vendor)
            }
        }
        .tabViewStyle(.page)
        .task {
            if let cached = TRStatusCache.shared.cached { status = cached }
            status = await TRProviders.fetchAll(using: TRSettings.shared)
        }
    }

    private var vendors: [String] {
        var seen: [String] = []
        for r in status.rings where !seen.contains(r.vendor ?? r.id) {
            seen.append(r.vendor ?? r.id)
        }
        return seen
    }

    private func rings(for vendor: String) -> [TRRing] {
        status.rings.filter { ($0.vendor ?? $0.id) == vendor }
    }
}

struct OverviewPage: View {
    let rings: [TRRing]

    var body: some View {
        VStack(spacing: 10) {
            RingStackView(rings: rings, outerDiameter: 96)
            ScrollView {
                VStack(spacing: 8) {
                    ForEach(rings) { ring in BarRow(ring: ring) }
                }
            }
        }
    }
}

struct VendorPage: View {
    let rings: [TRRing]
    let vendor: String

    var body: some View {
        ScrollView {
            VStack(spacing: 12) {
                Text(displayName)
                    .font(.system(size: 15, weight: .bold))
                    .frame(maxWidth: .infinity, alignment: .leading)
                ForEach(rings) { ring in BarRow(ring: ring) }
            }
            .padding(.horizontal, 4)
        }
    }

    private var displayName: String {
        (rings.first?.label ?? vendor).components(separatedBy: " ").first ?? vendor
    }
}
