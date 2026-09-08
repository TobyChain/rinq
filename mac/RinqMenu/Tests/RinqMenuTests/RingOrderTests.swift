import XCTest
@testable import RinqMenu

final class RingOrderTests: XCTestCase {
    func testMovingDownPlacesDraggedRingAfterEnteredRow() {
        let rings = [ring("a"), ring("b"), ring("c")]
        XCTAssertEqual(
            RingOrder.moving(rings, draggedID: "a", before: "b").map(\.id),
            ["b", "a", "c"]
        )
    }

    func testMovingUpPlacesDraggedRingBeforeEnteredRow() {
        let rings = [ring("a"), ring("b"), ring("c")]
        XCTAssertEqual(
            RingOrder.moving(rings, draggedID: "c", before: "a").map(\.id),
            ["c", "a", "b"]
        )
    }

    func testUnknownOrSameRingLeavesOrderUnchanged() {
        let rings = [ring("a"), ring("b")]
        XCTAssertEqual(RingOrder.moving(rings, draggedID: "a", before: "a"), rings)
        XCTAssertEqual(RingOrder.moving(rings, draggedID: "x", before: "b"), rings)
    }

    private func ring(_ id: String) -> Ring {
        Ring(
            id: id, label: id, vendor: nil, kind: "window", usedPercent: 0,
            remainingPercent: nil, remaining: nil, currency: nil, resetsAt: nil,
            accent: "blue", spentUsd: nil, budgetUsd: nil, usedValue: 0,
            totalValue: 100, valueUnit: "percent", status: nil
        )
    }
}
