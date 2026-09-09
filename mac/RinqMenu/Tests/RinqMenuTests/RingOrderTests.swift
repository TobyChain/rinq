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

final class PopoverLayoutTests: XCTestCase {
    func testUpToFiveRingsUseOneColumn() {
        let layout = PopoverLayout.make(
            ringCount: 5,
            visibleScreenSize: CGSize(width: 1440, height: 900)
        )
        XCTAssertEqual(layout.columns, 1)
        XCTAssertLessThanOrEqual(layout.height, 450)
        XCTAssertFalse(layout.scrolls)
    }

    func testSixOrMoreRingsUseTwoColumns() {
        let layout = PopoverLayout.make(
            ringCount: 8,
            visibleScreenSize: CGSize(width: 1440, height: 900)
        )
        XCTAssertEqual(layout.columns, 2)
        XCTAssertEqual(layout.width, 620)
        XCTAssertLessThanOrEqual(layout.height, 450)
        XCTAssertFalse(layout.scrolls)
    }

    func testHeightNeverExceedsHalfScreen() {
        let layout = PopoverLayout.make(
            ringCount: 30,
            visibleScreenSize: CGSize(width: 1000, height: 700)
        )
        XCTAssertLessThanOrEqual(layout.height + 28, 350)
        XCTAssertTrue(layout.scrolls)
    }
}

final class MenuRingLayoutTests: XCTestCase {
    @MainActor
    func testMenuIconPreservesPerRingColors() {
        XCTAssertFalse(AppDelegate.ringImage(pcts: [10, 50, 90]).isTemplate)
    }

    func testEmptyStateStillCreatesOneVisibleRing() {
        let layout = MenuRingLayout.make(ringCount: 0)
        XCTAssertGreaterThan(layout.lineWidth, 2)
        XCTAssertGreaterThan(layout.outerRadius, layout.lineWidth)
    }

    func testFiveRingsRemainVisible() {
        let layout = MenuRingLayout.make(ringCount: 5)
        let innermostCenter = layout.outerRadius - 4 * (layout.lineWidth + layout.gap)
        XCTAssertGreaterThan(layout.lineWidth, 1)
        XCTAssertGreaterThan(innermostCenter, layout.lineWidth / 2)
    }

    func testManyRingsStayInsideIcon() {
        let layout = MenuRingLayout.make(ringCount: 8)
        let innermostCenter = layout.outerRadius - 7 * (layout.lineWidth + layout.gap)
        XCTAssertGreaterThanOrEqual(layout.lineWidth, 0.55)
        XCTAssertGreaterThan(innermostCenter, layout.lineWidth / 2)
    }
}
