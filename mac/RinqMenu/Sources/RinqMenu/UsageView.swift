import SwiftUI

struct UsageView: View {
    @ObservedObject var store: Store

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                if let usage = store.usage {
                    UsageSummaryCard(title: "Today", subtitle: usage.today.date,
                                     input: usage.today.inputTokens,
                                     output: usage.today.outputTokens,
                                     requests: usage.today.requests)
                    UsageSummaryCard(title: "Last \(usage.daily.count) days",
                                     subtitle: "\(usage.week.startDate) – \(usage.week.endDate)",
                                     input: usage.week.inputTokens,
                                     output: usage.week.outputTokens,
                                     requests: usage.week.requests)
                    DailyUsageView(days: usage.daily)
                    AppUsageView(apps: usage.apps)
                    UsageSourcesView(sources: usage.sources)
                } else {
                    UsageEmptyView()
                }
            }
            .padding(14)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

private struct UsageSummaryCard: View {
    let title: String
    let subtitle: String
    let input: Int
    let output: Int
    let requests: Int

    var body: some View {
        VStack(alignment: .leading, spacing: 9) {
            HStack(alignment: .firstTextBaseline) {
                Text(title)
                    .font(.system(size: 15, weight: .semibold))
                Spacer()
                Text("\(requests) requests")
                    .font(.system(size: 10))
                    .foregroundStyle(.secondary)
            }
            Text(subtitle)
                .font(.system(size: 10))
                .foregroundStyle(.secondary)
            HStack(spacing: 8) {
                UsageMetric(label: "Input", value: input, color: .blue)
                UsageMetric(label: "Output", value: output, color: .purple)
            }
        }
        .padding(12)
        .background(Color.primary.opacity(0.06), in: RoundedRectangle(cornerRadius: 12))
    }
}

private struct UsageMetric: View {
    let label: String
    let value: Int
    let color: Color

    var body: some View {
        HStack(spacing: 6) {
            Circle().fill(color).frame(width: 7, height: 7)
            VStack(alignment: .leading, spacing: 1) {
                Text(label.uppercased())
                    .font(.system(size: 9, weight: .medium))
                    .foregroundStyle(.secondary)
                Text(formatTokenCount(value))
                    .font(.system(size: 16, weight: .bold, design: .rounded))
            }
            Spacer(minLength: 0)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

private struct DailyUsageView: View {
    let days: [UsageDay]
    @State private var hoveredDayID: String?

    private var maximum: Int {
        max(days.map(\.inputOutputTokens).max() ?? 0, 1)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 9) {
            Text("Daily usage")
                .font(.system(size: 13, weight: .semibold))
            Group {
                if let day = days.first(where: { $0.id == hoveredDayID }) {
                    HStack(spacing: 10) {
                        Text(day.date)
                            .foregroundStyle(.secondary)
                        Spacer(minLength: 4)
                        exactUsageLabel("Input", value: day.inputTokens, color: .blue)
                        exactUsageLabel("Output", value: day.outputTokens, color: .purple)
                    }
                } else {
                    Text("Hover a day to see exact input and output usage")
                        .foregroundStyle(.tertiary)
                }
            }
            .font(.system(size: 9, design: .rounded))
            .frame(height: 12)
            HStack(alignment: .bottom, spacing: 7) {
                ForEach(days) { day in
                    VStack(spacing: 4) {
                        HStack(alignment: .bottom, spacing: 2) {
                            usageBar(day.inputTokens, color: .blue)
                            usageBar(day.outputTokens, color: .purple)
                        }
                        .frame(height: 76, alignment: .bottom)
                        Text(shortDate(day.date))
                            .font(.system(size: 9))
                            .foregroundStyle(.secondary)
                            .lineLimit(1)
                    }
                    .frame(maxWidth: .infinity)
                    .contentShape(Rectangle())
                    .onHover { hovering in
                        if hovering {
                            hoveredDayID = day.id
                        } else if hoveredDayID == day.id {
                            hoveredDayID = nil
                        }
                    }
                }
            }
            HStack(spacing: 12) {
                Legend(color: .blue, label: "Input")
                Legend(color: .purple, label: "Output")
                Spacer()
            }
        }
        .padding(12)
        .background(Color.primary.opacity(0.04), in: RoundedRectangle(cornerRadius: 12))
    }

    private func usageBar(_ value: Int, color: Color) -> some View {
        RoundedRectangle(cornerRadius: 2)
            .fill(color.opacity(0.85))
            .frame(height: max(3, 70 * CGFloat(value) / CGFloat(maximum)))
    }

    private func exactUsageLabel(_ label: String, value: Int, color: Color) -> some View {
        HStack(spacing: 3) {
            Circle().fill(color).frame(width: 5, height: 5)
            Text("\(label) \(value.formatted())")
                .foregroundStyle(.primary)
        }
    }

    private func shortDate(_ value: String) -> String {
        String(value.dropFirst(5))
    }
}

private struct Legend: View {
    let color: Color
    let label: String

    var body: some View {
        HStack(spacing: 4) {
            Circle().fill(color).frame(width: 6, height: 6)
            Text(label).font(.system(size: 9)).foregroundStyle(.secondary)
        }
    }
}

private struct AppUsageView: View {
    let apps: [UsageApp]

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("By app")
                .font(.system(size: 13, weight: .semibold))
            if apps.isEmpty {
                Text("No local coding-agent usage found in the lookback window.")
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
            } else {
                ForEach(apps) { app in
                    HStack(spacing: 8) {
                        Image(systemName: appIcon(app.app))
                            .frame(width: 16)
                            .foregroundStyle(.secondary)
                        Text(app.app)
                            .font(.system(size: 11, weight: .medium))
                            .lineLimit(1)
                        Spacer()
                        VStack(alignment: .trailing, spacing: 1) {
                            Text("in \(formatTokenCount(app.inputTokens)) · out \(formatTokenCount(app.outputTokens))")
                                .font(.system(size: 10, weight: .semibold, design: .rounded))
                            Text("\(app.requests) requests")
                                .font(.system(size: 9))
                                .foregroundStyle(.secondary)
                        }
                    }
                    .padding(.vertical, 3)
                }
            }
        }
        .padding(12)
        .background(Color.primary.opacity(0.04), in: RoundedRectangle(cornerRadius: 12))
    }

    private func appIcon(_ app: String) -> String {
        if app.localizedCaseInsensitiveContains("claude") { return "bubble.left.and.bubble.right" }
        if app.localizedCaseInsensitiveContains("trae") { return "wand.and.stars" }
        if app.localizedCaseInsensitiveContains("ide") { return "chevron.left.forwardslash.chevron.right" }
        return "terminal"
    }
}

private struct UsageSourcesView: View {
    let sources: [UsageSourceStatus]

    var body: some View {
        if !sources.isEmpty {
            HStack(spacing: 6) {
                Image(systemName: "lock.shield")
                Text("Local only · \(sources.map(sourceName).joined(separator: ", "))")
            }
            .font(.system(size: 9))
            .foregroundStyle(.secondary)
        }
    }

    private func sourceName(_ source: UsageSourceStatus) -> String {
        switch source.adapter {
        case "claude_code": return "Claude Code"
        case "cc_switch": return "cc-switch"
        case "traex": return "TraeX"
        case "codex": return "Codex"
        default: return source.adapter
        }
    }
}

private struct UsageEmptyView: View {
    var body: some View {
        VStack(spacing: 10) {
            Image(systemName: "chart.bar.xaxis")
                .font(.system(size: 28))
                .foregroundStyle(.secondary)
            Text("No local usage yet")
                .font(.system(size: 14, weight: .semibold))
            Text("Rinq reads token counters from local Codex, TraeX, and Claude Code logs. Web sessions are not included.")
                .font(.system(size: 11))
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .frame(maxWidth: 300)
        }
        .frame(maxWidth: .infinity, minHeight: 180)
    }
}

private func formatTokenCount(_ value: Int) -> String {
    let number = Double(value)
    if number >= 1_000_000_000 { return String(format: "%.1fB", number / 1_000_000_000) }
    if number >= 1_000_000 { return String(format: "%.1fM", number / 1_000_000) }
    if number >= 1_000 { return String(format: "%.1fK", number / 1_000) }
    return "\(value)"
}
