import WidgetKit
import SwiftUI

struct RinqEntry: TimelineEntry {
    let date: Date
    let status: TRStatus?
}

struct RinqProvider: TimelineProvider {
    func placeholder(in context: Context) -> RinqEntry {
        RinqEntry(date: Date(), status: .sample)
    }

    func getSnapshot(in context: Context, completion: @escaping (RinqEntry) -> Void) {
        completion(RinqEntry(date: Date(), status: TRStatusCache.shared.cached ?? .sample))
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<RinqEntry>) -> Void) {
        Task {
            let status = await TRProviders.fetchAll(using: TRSettings.shared)
            let entry = RinqEntry(date: Date(), status: status)
            // Widgets are system-scheduled; ask for a refresh in 15 minutes.
            let next = Calendar.current.date(byAdding: .minute, value: 15, to: Date()) ?? Date().addingTimeInterval(900)
            completion(Timeline(entries: [entry], policy: .after(next)))
        }
    }
}

struct RinqWidgetView: View {
    var entry: RinqEntry
    @Environment(\.widgetFamily) private var family

    var body: some View {
        let rings = entry.status?.rings ?? TRStatus.sample.rings
        switch family {
        case .accessoryCircular:
            ZStack {
                RingStackView(rings: rings, outerDiameter: 62)
            }
            .containerBackground(for: .widget) { Color.clear }
        case .accessoryRectangular:
            VStack(alignment: .leading, spacing: 3) {
                ForEach(Array(rings.prefix(3))) { ring in
                    HStack(spacing: 6) {
                        Circle()
                            .stroke(TRPalette.color(ring.accent), lineWidth: 3)
                            .frame(width: 10, height: 10)
                        Text(ring.label).font(.system(size: 12, weight: .semibold))
                        Spacer()
                        Text(valueText(ring)).font(.system(size: 12, weight: .bold, design: .rounded))
                    }
                }
            }
            .containerBackground(for: .widget) { Color.clear }
        default:
            VStack(spacing: 8) {
                RingStackView(rings: rings, outerDiameter: 96)
                Text("Rinq").font(.caption2).foregroundStyle(.secondary)
            }
            .containerBackground(for: .widget) { Color.clear }
        }
    }

    private func valueText(_ ring: TRRing) -> String {
        ring.usageText
    }
}

@main
struct RinqWidget: Widget {
    let kind = "RinqWidget"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: RinqProvider()) { entry in
            RinqWidgetView(entry: entry)
        }
        .configurationDisplayName("Rinq")
        .description("AI quota rings")
        .supportedFamilies([
            .systemSmall,
            .accessoryCircular,
            .accessoryRectangular,
            .accessoryInline,
        ])
    }
}
