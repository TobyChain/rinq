import XCTest
@testable import RinqMenu

final class RingOrderTests: XCTestCase {
    func testMovingDownUsesTableDropRowSemantics() {
        let rings = [ring("a"), ring("b"), ring("c")]
        XCTAssertEqual(
            RingOrder.moving(rings, from: 0, toDropRow: 2).map(\.id),
            ["b", "a", "c"]
        )
    }

    func testMovingUpUsesTableDropRowSemantics() {
        let rings = [ring("a"), ring("b"), ring("c")]
        XCTAssertEqual(
            RingOrder.moving(rings, from: 2, toDropRow: 0).map(\.id),
            ["c", "a", "b"]
        )
    }

    func testDroppingAtEndMovesRingToLastPosition() {
        let rings = [ring("a"), ring("b"), ring("c")]
        XCTAssertEqual(
            RingOrder.moving(rings, from: 0, toDropRow: 3).map(\.id),
            ["b", "c", "a"]
        )
    }

    func testInvalidSourceLeavesOrderUnchanged() {
        let rings = [ring("a"), ring("b")]
        XCTAssertEqual(RingOrder.moving(rings, from: 4, toDropRow: 0), rings)
    }

    private func ring(_ id: String) -> Ring {
        Ring(
            id: id, label: id, vendor: nil, kind: "window", usedPercent: 0,
            remainingPercent: nil, remaining: nil, currency: nil, resetsAt: nil,
            windowMins: 300, accent: "blue", spentUsd: nil, budgetUsd: nil, usedValue: 0,
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

final class MenuBarLayoutTests: XCTestCase {
    @MainActor
    func testMenuIconPreservesPerBarColors() {
        XCTAssertFalse(AppDelegate.progressBarImage(
            pcts: [10, 50, 90], alertLevels: [nil, .warning, .critical]
        ).isTemplate)
    }

    func testEmptyStateStillCreatesOneVisibleBar() {
        let layout = MenuBarLayout.make(ringCount: 0)
        XCTAssertEqual(layout.barHeight, 3)
        XCTAssertEqual(layout.barWidth, 22)
    }

    func testFiveBarsRemainReadable() {
        let layout = MenuBarLayout.make(ringCount: 5)
        XCTAssertGreaterThanOrEqual(layout.barHeight, 2)
        XCTAssertEqual(layout.gap, 1)
    }

    func testManyBarsStayInsideIcon() {
        let count = 8
        let layout = MenuBarLayout.make(ringCount: count)
        let contentHeight = CGFloat(count) * layout.barHeight
            + CGFloat(count - 1) * layout.gap
        XCTAssertGreaterThanOrEqual(layout.barHeight, 1)
        XCTAssertLessThanOrEqual(layout.top * 2 + contentHeight, 18)
    }
}

final class QuotaAlertTests: XCTestCase {
    func testExhaustedQuotaIsCritical() {
        var monitor = QuotaAlertMonitor(defaults: isolatedDefaults())
        let result = monitor.evaluate(rings: [ring("codex-5h", used: 100, window: 300)])
        XCTAssertEqual(result.active.first?.reason, .exhausted)
        XCTAssertEqual(result.active.first?.level, .critical)
        XCTAssertTrue(result.shouldPresent)
    }

    func testFiveHourLowQuotaIsWarning() {
        var monitor = QuotaAlertMonitor(defaults: isolatedDefaults())
        let result = monitor.evaluate(rings: [ring("codex-5h", used: 71, window: 300)])
        XCTAssertEqual(result.active.first?.reason, .lowQuota)
        XCTAssertEqual(result.active.first?.level, .warning)
    }

    func testWeeklyLowQuotaUsesTenPercentThreshold() {
        var monitor = QuotaAlertMonitor(defaults: isolatedDefaults())
        let result = monitor.evaluate(rings: [ring("codex-week", used: 91, window: 10080)])
        XCTAssertEqual(result.active.first?.reason, .lowQuota)
    }

    func testRapidUsageRequiresMoreThanTwentyPercentInThirtyMinutes() {
        var monitor = QuotaAlertMonitor(defaults: isolatedDefaults())
        let start = Date(timeIntervalSince1970: 1_000_000)
        _ = monitor.evaluate(rings: [ring("codex-5h", used: 10, window: 300)], now: start)
        let result = monitor.evaluate(
            rings: [ring("codex-5h", used: 31, window: 300)],
            now: start.addingTimeInterval(30 * 60)
        )
        XCTAssertEqual(result.active.first?.reason, .rapidUsage)
        XCTAssertTrue(result.shouldPresent)
    }

    func testExistingAlertDoesNotPresentAgainUntilItResets() {
        var monitor = QuotaAlertMonitor(defaults: isolatedDefaults())
        let ring = ring("codex-5h", used: 100, window: 300)
        XCTAssertTrue(monitor.evaluate(rings: [ring]).shouldPresent)
        XCTAssertFalse(monitor.evaluate(rings: [ring]).shouldPresent)
    }

    private func isolatedDefaults() -> UserDefaults {
        let suite = "rinq-alert-tests-\(UUID().uuidString)"
        return UserDefaults(suiteName: suite)!
    }

    private func ring(_ id: String, used: Int, window: Int) -> Ring {
        Ring(
            id: id, label: id, vendor: "codex", kind: "window", usedPercent: used,
            remainingPercent: 100 - used, remaining: nil, currency: nil, resetsAt: nil,
            windowMins: window, accent: "blue", spentUsd: nil, budgetUsd: nil,
            usedValue: Double(used), totalValue: 100, valueUnit: "percent", status: nil
        )
    }
}
