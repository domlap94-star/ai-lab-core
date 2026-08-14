#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 1 ]; then
  echo "Usage:"
  echo "./scripts/build-ios.sh https://your-ai-lab-host 1.0.0 1"
  exit 1
fi

API_BASE_URL="${1%/}"
VERSION="${2:-1.0.0}"
BUILD_NUMBER="${3:-1}"

cd "$(dirname "$0")/.."

flutter pub get

flutter build ios \
  --release \
  --build-name="$VERSION" \
  --build-number="$BUILD_NUMBER" \
  --dart-define="API_BASE_URL=$API_BASE_URL"

echo
echo "iOS Flutter build complete."
echo "Open ios/Runner.xcworkspace in Xcode for signing/archive."
