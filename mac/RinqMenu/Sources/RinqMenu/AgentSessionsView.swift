import SwiftUI

/// Expanded view of sessions that are still open in a local terminal agent.
/// The daemon has already grouped them by CLI and state; the panel preserves
/// that order while making the project, model, path, and latest message visible.
struct AgentSessionsPanel: View {
    let snapshot: SessionSnapshot

    private var openSessions: [AgentSession] {
        snapshot.sessions.filter { $0.isOpen == true }
    }

    var body: some View {
        VStack(spacing: 0) {
            header
            ScrollView(.vertical, showsIndicators: openSessions.count > PopoverLayout.maxAgentRows) {
                LazyVStack(spacing: 0) {
                    ForEach(openSessions) { session in
                        AgentSessionRow(session: session)
                    }
                }
            }
            .frame(maxHeight: .infinity)
        }
        .padding(.horizontal, 12)
        .frame(height: panelHeight)
        .accessibilityElement(children: .contain)
    }

    private var panelHeight: CGFloat {
        PopoverLayout.agentHeaderHeight
            + CGFloat(min(openSessions.count, PopoverLayout.maxAgentRows)) * PopoverLayout.agentSessionRowHeight
            + 8
    }

    private var header: some View {
        HStack(spacing: 8) {
            Text("Open sessions")
                .font(.system(size: 12, weight: .semibold))
            Text("\(openSessions.count)")
                .font(.system(size: 11, weight: .bold, design: .rounded))
                .foregroundStyle(.secondary)
            Spacer(minLength: 6)
            SessionCount(label: "run", value: snapshot.counts?.running ?? 0, color: .blue)
            SessionCount(label: "sub", value: snapshot.counts?.subagentsRunning ?? 0, color: .purple)
            SessionCount(label: "wait", value: snapshot.counts?.waiting ?? 0, color: .orange)
            SessionCount(label: "idle", value: snapshot.counts?.idle ?? 0, color: .secondary)
        }
        .frame(height: PopoverLayout.agentHeaderHeight)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(openSessions.count) open agent sessions")
    }
}

private struct SessionCount: View {
    let label: String
    let value: Int
    let color: Color

    var body: some View {
        HStack(spacing: 3) {
            Circle().fill(color).frame(width: 6, height: 6)
            Text("\(value)")
                .font(.system(size: 10, weight: .bold, design: .rounded))
            Text(label)
                .font(.system(size: 9))
                .foregroundStyle(.secondary)
        }
        .help("\(value) \(label)")
    }
}

private struct AgentSessionRow: View {
    let session: AgentSession

    var body: some View {
        HStack(alignment: .top, spacing: 9) {
            Circle()
                .fill(stateColor)
                .frame(width: 8, height: 8)
                .padding(.top, 5)

            VStack(alignment: .leading, spacing: 3) {
                HStack(spacing: 6) {
                    Text(session.app)
                        .font(.system(size: 9, weight: .bold, design: .rounded))
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                    Text(session.project ?? "session")
                        .font(.system(size: 12, weight: .semibold))
                        .lineLimit(1)
                    Spacer(minLength: 4)
                    Text(stateLabel)
                        .font(.system(size: 10, weight: .medium))
                        .foregroundStyle(stateColor)
                }

                Text(session.summary ?? "")
                    .font(.system(size: 10))
                    .foregroundStyle(.primary.opacity(0.82))
                    .lineLimit(1)

                HStack(spacing: 7) {
                    if let model = session.model, !model.isEmpty {
                        Label(model, systemImage: "cpu")
                    }
                    if let cwd = session.cwd, !cwd.isEmpty {
                        Label(shortPath(cwd), systemImage: "folder")
                    }
                    Spacer(minLength: 2)
                    if let updated = session.updatedAt {
                        Text(relativeTime(updated))
                    }
                }
                .font(.system(size: 9, design: .monospaced))
                .foregroundStyle(.secondary)
                .lineLimit(1)
            }
        }
        .padding(.horizontal, 10)
        .frame(height: PopoverLayout.agentSessionRowHeight)
        .background(stateColor.opacity(0.045), in: RoundedRectangle(cornerRadius: 8))
        .overlay(alignment: .bottom) {
            Rectangle()
                .fill(Color.primary.opacity(0.06))
                .frame(height: 1)
                .padding(.leading, 17)
        }
        .help(tooltip)
        .accessibilityElement(children: .combine)
        .accessibilityLabel(accessibilityText)
    }

    private var stateColor: Color {
        switch session.state {
        case "running": return .blue
        case "subagents_running": return .purple
        case "waiting": return .orange
        case "failed": return .red
        default: return .secondary
        }
    }

    private var stateLabel: String {
        switch session.state {
        case "running": return "running"
        case "subagents_running": return "subagents running"
        case "waiting": return "waiting"
        case "idle": return "idling"
        case "failed": return "failed"
        default: return session.state
        }
    }

    private var tooltip: String {
        var lines = ["\(session.app) · \(session.project ?? "session")", stateLabel]
        if let cwd = session.cwd { lines.append(cwd) }
        if let model = session.model { lines.append(model) }
        if let summary = session.summary, !summary.isEmpty { lines.append(summary) }
        return lines.joined(separator: "\n")
    }

    private var accessibilityText: String {
        "\(session.app) \(session.project ?? "session"), \(stateLabel), \(session.summary ?? "")"
    }

    private func shortPath(_ path: String) -> String {
        let home = FileManager.default.homeDirectoryForCurrentUser.path
        if path.hasPrefix(home) { return "~" + path.dropFirst(home.count) }
        return path
    }

    private func relativeTime(_ timestamp: Int) -> String {
        let seconds = max(0, Int(Date().timeIntervalSince1970) - timestamp)
        if seconds < 60 { return "now" }
        let minutes = seconds / 60
        if minutes < 60 { return "\(minutes)m" }
        let hours = minutes / 60
        if hours < 24 { return "\(hours)h" }
        return "\(hours / 24)d"
    }
}
