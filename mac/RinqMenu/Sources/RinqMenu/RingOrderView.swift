import AppKit
import SwiftUI

private let ringPasteboardType = NSPasteboard.PasteboardType("com.tobychain.rinq.ring-order")

struct RingOrderView: View {
    @ObservedObject var store: Store
    let rings: [Ring]

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Drag any row to reorder. Rings and the menu icon update after drop.")
                .font(.system(size: 10))
                .foregroundStyle(.secondary)

            RingOrderTable(rings: rings) { ids in
                Task { await store.saveRingOrder(ids) }
            }
            .frame(height: CGFloat(max(rings.count, 1)) * 34)
        }
    }
}

private struct RingOrderTable: NSViewRepresentable {
    let rings: [Ring]
    let onReorder: ([String]) -> Void

    func makeCoordinator() -> Coordinator {
        Coordinator(rings: rings, onReorder: onReorder)
    }

    func makeNSView(context: Context) -> NSScrollView {
        let table = NSTableView()
        let column = NSTableColumn(identifier: NSUserInterfaceItemIdentifier("ring"))
        column.resizingMask = .autoresizingMask
        table.addTableColumn(column)
        table.headerView = nil
        table.backgroundColor = .clear
        table.rowHeight = 32
        table.intercellSpacing = NSSize(width: 0, height: 2)
        table.selectionHighlightStyle = .none
        table.allowsEmptySelection = true
        table.dataSource = context.coordinator
        table.delegate = context.coordinator
        table.registerForDraggedTypes([ringPasteboardType])
        table.setDraggingSourceOperationMask(.move, forLocal: true)

        let scroll = NSScrollView()
        scroll.drawsBackground = false
        scroll.hasVerticalScroller = false
        scroll.hasHorizontalScroller = false
        scroll.borderType = .noBorder
        scroll.documentView = table
        context.coordinator.tableView = table
        return scroll
    }

    func updateNSView(_ scroll: NSScrollView, context: Context) {
        context.coordinator.onReorder = onReorder
        context.coordinator.update(rings: rings)
    }

    final class Coordinator: NSObject, NSTableViewDataSource, NSTableViewDelegate {
        var rings: [Ring]
        var onReorder: ([String]) -> Void
        weak var tableView: NSTableView?
        private var draggedID: String?

        init(rings: [Ring], onReorder: @escaping ([String]) -> Void) {
            self.rings = rings
            self.onReorder = onReorder
        }

        func update(rings newRings: [Ring]) {
            guard draggedID == nil, rings.map(\.id) != newRings.map(\.id) else { return }
            rings = newRings
            tableView?.reloadData()
        }

        func numberOfRows(in tableView: NSTableView) -> Int { rings.count }

        func tableView(
            _ tableView: NSTableView,
            viewFor tableColumn: NSTableColumn?,
            row: Int
        ) -> NSView? {
            guard rings.indices.contains(row) else { return nil }
            let cell = NSTableCellView()
            let content = NSHostingView(rootView: RingOrderRow(ring: rings[row]))
            content.translatesAutoresizingMaskIntoConstraints = false
            cell.addSubview(content)
            NSLayoutConstraint.activate([
                content.leadingAnchor.constraint(equalTo: cell.leadingAnchor),
                content.trailingAnchor.constraint(equalTo: cell.trailingAnchor),
                content.topAnchor.constraint(equalTo: cell.topAnchor),
                content.bottomAnchor.constraint(equalTo: cell.bottomAnchor),
            ])
            return cell
        }

        func tableView(_ tableView: NSTableView, pasteboardWriterForRow row: Int) -> NSPasteboardWriting? {
            guard rings.indices.contains(row) else { return nil }
            draggedID = rings[row].id
            let item = NSPasteboardItem()
            item.setString(rings[row].id, forType: ringPasteboardType)
            return item
        }

        func tableView(
            _ tableView: NSTableView,
            validateDrop info: NSDraggingInfo,
            proposedRow row: Int,
            proposedDropOperation dropOperation: NSTableView.DropOperation
        ) -> NSDragOperation {
            guard info.draggingSource as? NSTableView === tableView else { return [] }
            tableView.setDropRow(row, dropOperation: .above)
            return .move
        }

        func tableView(
            _ tableView: NSTableView,
            acceptDrop info: NSDraggingInfo,
            row: Int,
            dropOperation: NSTableView.DropOperation
        ) -> Bool {
            guard let id = info.draggingPasteboard.string(forType: ringPasteboardType),
                  let source = rings.firstIndex(where: { $0.id == id }) else { return false }

            rings = RingOrder.moving(rings, from: source, toDropRow: row)
            draggedID = nil
            tableView.reloadData()
            onReorder(rings.map(\.id))
            return true
        }

        func tableView(
            _ tableView: NSTableView,
            draggingSession session: NSDraggingSession,
            endedAt screenPoint: NSPoint,
            operation: NSDragOperation
        ) {
            draggedID = nil
        }
    }
}

private struct RingOrderRow: View {
    let ring: Ring

    var body: some View {
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
        .padding(.horizontal, 7)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color.clear)
    }
}
