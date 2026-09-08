.PHONY: watch-generate watch-build watch-sim mac-test install

watch-generate:
	cd watch && xcodegen generate

watch-build: watch-generate
	cd watch && xcodebuild \
		-project Rinq.xcodeproj \
		-scheme RinqWatch \
		-configuration Debug \
		-destination 'generic/platform=watchOS Simulator' \
		CODE_SIGNING_ALLOWED=NO \
		build

watch-sim: watch-generate
	@watch/scripts/sim.sh

mac-test:
	cd mac && python3 -m unittest test_rinq -v

install:
	./install.sh
