import WidgetKit
import SwiftUI

struct RinqWatchEntry: TimelineEntry {
    let date: Date
    let status: TRStatus?
}

struct RinqWatchProvider: TimelineProvider {
    func placeholder(in context: Context) -> RinqWatchEntry {
        RinqWatchEntry(date: Date(), status: .sample)
    }

    func getSnapshot(in context: Context, completion: @escaping (RinqWatchEntry) -> Void) {
        completion(RinqWatchEntry(date: Date(), status: TRStatusCache.shared.cached ?? .sample))
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<RinqWatchEntry>) -> Void) {
        Task {
            let status = await TRProviders.fetchAll(using: TRSettings.shared)
            let entry = RinqWatchEntry(date: Date(), status: status)
            let next = Calendar.current.date(byAdding: .minute, value: 15, to: Date()) ?? Date().addingTimeInterval(900)
            completion(Timeline(entries: [entry], policy: .after(next)))
        }
    }
}

struct RinqWatchWidgetView: View {
    var entry: RinqWatchEntry

    var body: some View {
        let rings = entry.status?.rings ?? TRStatus.sample.rings
        ZStack {
            RingStackView(rings: rings)
        }
        .containerBackground(for: .widget) { Color.clear }
    }
}

@main
struct RinqWatchWidget: Widget {
    let kind = "RinqWatchWidget"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: RinqWatchProvider()) { entry in
            RinqWatchWidgetView(entry: entry)
        }
        .configurationDisplayName("Rinq")
        .description("AI quota rings")
        .supportedFamilies([
            .accessoryCircular,
            .accessoryCorner,
            .accessoryRectangular,
        ])
    }
}
