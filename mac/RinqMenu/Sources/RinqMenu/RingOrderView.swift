import SwiftUI
import UniformTypeIdentifiers

struct RingOrderView: View {
    @ObservedObject var store: Store
    let rings: [Ring]

    @State private var orderedRings: [Ring] = []
    @State private var draggedID: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Drag rows to reorder. Rings and the menu icon update after drop.")
                .font(.system(size: 10))
                .foregroundStyle(.secondary)

            ForEach(orderedRings) { ring in
                ringRow(ring)
                    .contentShape(Rectangle())
                    .onDrag {
                        draggedID = ring.id
                        return NSItemProvider(
                            item: ring.id as NSString,
                            typeIdentifier: UTType.plainText.identifier
                        )
                    } preview: {
                        ringRow(ring)
                            .padding(8)
                            .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 8))
                    }
                    .onDrop(
                        of: [UTType.plainText],
                        delegate: RingDropDelegate(
                            targetID: ring.id,
                            draggedID: $draggedID,
                            rings: $orderedRings,
                            didDrop: persistOrder
                        )
                    )
            }
        }
        .onAppear { syncFromStore() }
        .onChange(of: rings) { _ in
            guard draggedID == nil else { return }
            syncFromStore()
        }
    }

    private func ringRow(_ ring: Ring) -> some View {
        HStack(spacing: 9) {
            Image(systemName: "line.3.horizontal")
                .font(.system(size: 11, weight: .medium))
                .foregroundStyle(.secondary)
            Circle()
                .fill(Palette.color(ring.accent))
                .frame(width: 9, height: 9)
            Text(ring.label)
                .font(.system(size: 12))
            Spacer()
        }
        .padding(.vertical, 5)
        .padding(.horizontal, 7)
        .background(
            RoundedRectangle(cornerRadius: 7)
                .fill(draggedID == ring.id ? Color.accentColor.opacity(0.12) : Color.clear)
        )
    }

    private func syncFromStore() {
        orderedRings = rings
    }

    private func persistOrder() {
        let ids = orderedRings.map(\.id)
        Task { await store.saveRingOrder(ids) }
    }
}

private struct RingDropDelegate: DropDelegate {
    let targetID: String
    @Binding var draggedID: String?
    @Binding var rings: [Ring]
    let didDrop: () -> Void

    func dropEntered(info: DropInfo) {
        guard let draggedID, draggedID != targetID,
              rings.contains(where: { $0.id == draggedID }),
              rings.contains(where: { $0.id == targetID }) else { return }

        withAnimation(.easeInOut(duration: 0.16)) {
            rings = RingOrder.moving(rings, draggedID: draggedID, before: targetID)
        }
    }

    func dropUpdated(info: DropInfo) -> DropProposal? {
        DropProposal(operation: .move)
    }

    func performDrop(info: DropInfo) -> Bool {
        didDrop()
        draggedID = nil
        return true
    }
}
