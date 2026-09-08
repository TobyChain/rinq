import WidgetKit
import SwiftUI

struct TRRingEntry: TimelineEntry {
    let date: Date
    let status: TRStatus
}

struct TRRingProvider: TimelineProvider {
    func placeholder(in context: Context) -> TRRingEntry {
        TRRingEntry(date: Date(), status: .sample)
    }

    func getSnapshot(in context: Context, completion: @escaping (TRRingEntry) -> Void) {
        completion(TRRingEntry(date: Date(), status: .sample))
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<TRRingEntry>) -> Void) {
        Task {
            let status = (await TRStatusLoader.remote()) ?? .sample
            let entry = TRRingEntry(date: Date(), status: status)
            // watchOS budgets complication reloads; ask again in 15 minutes.
            let next = Calendar.current.date(byAdding: .minute, value: 15, to: Date()) ?? Date().addingTimeInterval(900)
            completion(Timeline(entries: [entry], policy: .after(next)))
        }
    }
}

struct TRRingWidgetView: View {
    var entry: TRRingEntry

    var body: some View {
        ZStack {
            RingStackView(rings: entry.status.rings)
            VStack(spacing: 1) {
                Text(headline)
                    .font(.system(size: 15, weight: .bold, design: .rounded))
                    .minimumScaleFactor(0.6)
                Text(caption)
                    .font(.system(size: 8, weight: .semibold))
                    .foregroundStyle(.secondary)
            }
        }
        .containerBackground(for: .widget) { Color.clear }
    }

    private var headline: String {
        let a = entry.status.agents
        if (a?.waiting ?? 0) > 0 { return "!\(a?.waiting ?? 0)" }
        return "\(a?.running ?? 0)"
    }

    private var caption: String {
        (entry.status.agents?.waiting ?? 0) > 0 ? "wait" : "run"
    }
}

@main
struct TRRingWidget: Widget {
    let kind = "TRRingWidget"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: TRRingProvider()) { entry in
            TRRingWidgetView(entry: entry)
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
