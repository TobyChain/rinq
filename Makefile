.PHONY: ios-generate ios-build ios-sim watch-generate watch-build mac-test install

# ---- iOS app + home/lock-screen widget (standalone, no Mac) -------------
ios-generate:
	cd app && xcodegen generate

ios-build: ios-generate
	cd app && xcodebuild \
		-project Rinq.xcodeproj \
		-scheme RinqApp \
		-configuration Debug \
		-destination 'generic/platform=iOS Simulator' \
		CODE_SIGNING_ALLOWED=NO \
		build

ios-sim:
	cd app && ./scripts/ios-sim.sh

# ---- watchOS app + complication ------------------------------------------
watch-generate:
	cd app && xcodegen generate

watch-build: watch-generate
	cd app && xcodebuild \
		-project Rinq.xcodeproj \
		-scheme RinqWatchApp \
		-configuration Debug \
		-destination 'generic/platform=watchOS Simulator' \
		CODE_SIGNING_ALLOWED=NO \
		build

# ---- Mac collector (optional local relay/daemon) -------------------------
mac-test:
	cd mac && python3 -m unittest test_rinq -v

install:
	./install.sh
