import AppKit
import SwiftUI
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
            totalValue: 100, valueUnit: "percent", status: nil, statusDetail: nil
        )
    }
}

final class RingPresentationTests: XCTestCase {
    func testStatusItemsDoNotBecomeMenuBarQuotaBars() {
        let quota = ring(id: "codex-5h", used: 25, status: nil)
        let status = ring(id: "zhipu-status", used: nil, status: "not_connected")
        XCTAssertEqual(RingPresentation.quotaRings([quota, status]).map(\.id), ["codex-5h"])
    }

    private func ring(id: String, used: Int?, status: String?) -> Ring {
        Ring(
            id: id, label: id, vendor: nil, kind: status == nil ? "window" : "status",
            usedPercent: used, remainingPercent: nil, remaining: nil, currency: nil,
            resetsAt: nil, windowMins: nil, accent: status == nil ? "blue" : "gray",
            spentUsd: nil, budgetUsd: nil, usedValue: used.map(Double.init),
            totalValue: used == nil ? nil : 100, valueUnit: used == nil ? nil : "percent",
            status: status, statusDetail: status == nil ? nil : "Connect an account"
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

    func testAlertLayoutReservesAVisibleSlot() {
        let size = CGSize(width: 1440, height: 900)
        let plain = PopoverLayout.make(ringCount: 4, visibleScreenSize: size)
        let alert = PopoverLayout.make(ringCount: 4, visibleScreenSize: size, hasAlerts: true)

        XCTAssertFalse(plain.reservesAlertSpace)
        XCTAssertTrue(alert.reservesAlertSpace)
        XCTAssertGreaterThan(alert.height, plain.height)
        XCTAssertLessThanOrEqual(alert.height + 28, 450)
    }

    func testAlertLayoutStaysIdenticalAfterDismissalUntilPopoverCloses() {
        var state = PopoverAlertLayoutState(hasAlerts: true)
        let size = CGSize(width: 1440, height: 900)
        let before = PopoverLayout.make(
            ringCount: 4, visibleScreenSize: size, hasAlerts: state.reservesAlertSpace
        )
        state.observe(hasAlerts: false)
        let after = PopoverLayout.make(
            ringCount: 4, visibleScreenSize: size, hasAlerts: state.reservesAlertSpace
        )

        XCTAssertTrue(state.reservesAlertSpace)
        XCTAssertEqual(after, before)
    }

    func testAlertSlotCanBeAddedWhilePopoverIsOpen() {
        var state = PopoverAlertLayoutState(hasAlerts: false)
        state.observe(hasAlerts: true)
        XCTAssertTrue(state.reservesAlertSpace)
    }

    func testLayoutReservesFooterHeight() {
        let size = CGSize(width: 1440, height: 900)
        let layout = PopoverLayout.make(ringCount: 4, visibleScreenSize: size)
        // The persistent quit footer must always fit inside the popover, so its
        // height is part of the fixed chrome regardless of ring count.
        XCTAssertGreaterThanOrEqual(layout.height, PopoverLayout.footerHeight)
        XCTAssertLessThanOrEqual(layout.height + 28, 450)
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

final class MainMenuTests: XCTestCase {
    // The accessory app needs a standard Edit menu so the API key field can
    // accept Cmd-V paste (and Cut/Copy/Select All). Verify the menu exposes the
    // clipboard actions with nil target and the expected key equivalents so
    // AppKit routes them to the first-responder text field.
    @MainActor
    func testEditMenuProvidesClipboardActions() {
        let editMenu = AppDelegate.makeMainMenu().items
            .compactMap(\.submenu)
            .first { $0.title == "Edit" }
        let paste = editMenu?.items.first { $0.action == #selector(NSText.paste(_:)) }

        XCTAssertNotNil(paste, "Edit menu must include a Paste item")
        XCTAssertEqual(paste?.keyEquivalent, "v")
        XCTAssertNil(paste?.target, "Paste must dispatch to the first responder")
        XCTAssertTrue(editMenu?.items.contains { $0.action == #selector(NSText.copy(_:)) } ?? false)
        XCTAssertTrue(editMenu?.items.contains { $0.action == #selector(NSText.cut(_:)) } ?? false)
        XCTAssertTrue(editMenu?.items.contains { $0.action == #selector(NSText.selectAll(_:)) } ?? false)
    }
}

final class PopoverBackgroundTests: XCTestCase {
    @MainActor
    func testBackgroundConfigurationDoesNotPaintContentSubviews() {
        let root = NSView()
        let effect = NSVisualEffectView()
        let content = NSView()
        let label = NSTextField(labelWithString: "Rinq")
        content.wantsLayer = true
        label.wantsLayer = true
        effect.addSubview(content)
        content.addSubview(label)
        root.addSubview(effect)

        AppDelegate.configurePopoverBackground(root)

        XCTAssertNotNil(root.layer?.backgroundColor)
        XCTAssertEqual(effect.material, .windowBackground)
        XCTAssertEqual(effect.blendingMode, .withinWindow)
        XCTAssertEqual(effect.state, .inactive)
        XCTAssertNil(content.layer?.backgroundColor)
        XCTAssertNil(label.layer?.backgroundColor)
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

    func testDismissedAlertStaysHiddenUntilConditionClears() {
        let defaults = isolatedDefaults()
        var monitor = QuotaAlertMonitor(defaults: defaults)
        let exhausted = ring("codex-5h", used: 100, window: 300)
        let first = monitor.evaluate(rings: [exhausted])

        monitor.dismiss(alertIDs: Set(first.active.map(\.id)))
        monitor = QuotaAlertMonitor(defaults: defaults)
        let dismissed = monitor.evaluate(rings: [exhausted])
        XCTAssertTrue(dismissed.active.isEmpty)
        XCTAssertFalse(dismissed.shouldPresent)

        _ = monitor.evaluate(rings: [ring("codex-5h", used: 40, window: 300)])
        let exhaustedAgain = monitor.evaluate(rings: [exhausted])
        XCTAssertEqual(exhaustedAgain.active.first?.reason, .exhausted)
        XCTAssertTrue(exhaustedAgain.shouldPresent)
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
            usedValue: Double(used), totalValue: 100, valueUnit: "percent", status: nil,
            statusDetail: nil
        )
    }
}

final class AlertDismissalTests: XCTestCase {
    @MainActor
    func testDismissAlertsAcknowledgesActiveAlertsOnlyOnce() {
        let suite = "rinq-store-alert-tests-\(UUID().uuidString)"
        let store = Store(alertDefaults: UserDefaults(suiteName: suite)!)
        store.alerts = [QuotaAlert(
            ringID: "codex-5h",
            label: "Codex 5h",
            level: .warning,
            reason: .lowQuota,
            message: "Codex 5h has 20% remaining"
        )]

        XCTAssertTrue(store.dismissAlerts())
        XCTAssertTrue(store.alerts.isEmpty)
        XCTAssertFalse(store.dismissAlerts())
    }

    @MainActor
    func testRenderedPopoverSizeStaysStableAfterDismissal() {
        let suite = "rinq-root-alert-tests-\(UUID().uuidString)"
        let store = Store(alertDefaults: UserDefaults(suiteName: suite)!)
        store.status = Status(rings: [Ring(
            id: "codex-5h", label: "Codex 5h", vendor: "codex", kind: "window",
            usedPercent: 80, remainingPercent: 20, remaining: nil, currency: nil,
            resetsAt: nil, windowMins: 300, accent: "blue", spentUsd: nil, budgetUsd: nil,
            usedValue: 80, totalValue: 100, valueUnit: "percent", status: nil, statusDetail: nil
        )], updatedAt: nil)
        store.alerts = [QuotaAlert(
            ringID: "codex-5h", label: "Codex 5h", level: .warning, reason: .lowQuota,
            message: "Codex 5h has 20% remaining"
        )]
        let root = RootView(
            store: store, visibleScreenSize: CGSize(width: 1440, height: 900),
            onLayoutChange: { _ in }, onAlertsDismissed: {}
        )
        let hosting = NSHostingView(rootView: root)
        hosting.layoutSubtreeIfNeeded()
        RunLoop.main.run(until: Date().addingTimeInterval(0.01))
        let before = hosting.fittingSize

        XCTAssertTrue(store.dismissAlerts())
        RunLoop.main.run(until: Date().addingTimeInterval(0.01))
        hosting.layoutSubtreeIfNeeded()

        XCTAssertEqual(hosting.fittingSize, before)
    }
}

final class UsageFormattingTests: XCTestCase {
    func testHoverTokenCountUsesThousandsBelowPointOneMillion() {
        XCTAssertEqual(formatHoverTokenCount(99_999), "100.0K")
        XCTAssertEqual(formatHoverTokenCount(12_345), "12.3K")
    }

    func testHoverTokenCountUsesMillionsAndBillionsWithOneDecimal() {
        XCTAssertEqual(formatHoverTokenCount(100_000), "0.1M")
        XCTAssertEqual(formatHoverTokenCount(1_250_000), "1.2M")
        XCTAssertEqual(formatHoverTokenCount(1_250_000_000), "1.2B")
    }
}
