#!/bin/bash
set -e

VERSION=$(python3 -c "import sys; sys.path.insert(0, '.'); from config import VERSION; print(VERSION)")
DMG_NAME="Conductor-${VERSION}.dmg"
IDENTITY="Developer ID Application: Geoffrey Kim (7Q7466822A)"
KEYCHAIN_PROFILE="AC_PASSWORD"
ENTITLEMENTS="$(dirname "$0")/entitlements.plist"

echo "==> Version: ${VERSION}"

echo "==> Installing build dependencies..."
pip install pyinstaller

echo "==> Building Conductor.app..."
pyinstaller conductor.spec --clean --noconfirm
echo "==> Build complete: dist/Conductor.app"

echo "==> Signing Conductor.app..."
codesign --force --deep --options runtime \
    --entitlements "${ENTITLEMENTS}" \
    --sign "${IDENTITY}" \
    --timestamp \
    dist/Conductor.app
echo "==> Signature applied"

echo "==> Verifying signature..."
codesign --verify --deep --strict dist/Conductor.app
echo "==> Signature verified"

if command -v create-dmg &> /dev/null; then
    echo "==> Creating ${DMG_NAME}..."
    rm -f "${DMG_NAME}"
    create-dmg \
        --volname "Conductor" \
        --volicon "dist/Conductor.app/Contents/Resources/icon-windowed.icns" \
        --window-pos 200 120 \
        --window-size 580 380 \
        --icon-size 100 \
        --icon "Conductor.app" 160 180 \
        --hide-extension "Conductor.app" \
        --app-drop-link 400 180 \
        "${DMG_NAME}" \
        "dist/Conductor.app" || true
    echo "==> ${DMG_NAME} ready"

    echo "==> Signing ${DMG_NAME}..."
    codesign --sign "${IDENTITY}" --timestamp "${DMG_NAME}"
    echo "==> DMG signed"

    echo "==> Notarizing ${DMG_NAME} (this may take a few minutes)..."
    xcrun notarytool submit "${DMG_NAME}" \
        --keychain-profile "${KEYCHAIN_PROFILE}" \
        --wait
    echo "==> Notarization complete"

    echo "==> Stapling ticket to ${DMG_NAME}..."
    xcrun stapler staple "${DMG_NAME}"
    echo "==> Stapled"

    echo "==> Final Gatekeeper check..."
    spctl --assess --type open --context context:primary-signature "${DMG_NAME}"
    echo "==> ${DMG_NAME} is ready to distribute"
else
    echo ""
    echo "  To also build a .dmg, install create-dmg:"
    echo "  brew install create-dmg"
    echo "  Then re-run this script."
fi

echo ""
echo "Done. Distribute ${DMG_NAME}."
