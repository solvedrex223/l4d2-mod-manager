#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

APP_NAME="l4d2-mod-manager"
VERSION="$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml | head -n1)"
OUT="dist/${APP_NAME}-${VERSION}-x86_64.AppImage"
CACHE="scripts/.cache"
APPIMAGETOOL_URL="https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"

echo "==> Building ${APP_NAME} ${VERSION} AppImage"

echo "==> Cleaning previous output"
rm -rf build dist
mkdir -p dist "${CACHE}"

if [ ! -f packaging/icon-256.png ]; then
    echo "==> Generating app icon"
    QT_QPA_PLATFORM=offscreen poetry run python scripts/make_icon.py
fi

echo "==> Running PyInstaller"
poetry run pyinstaller \
    --noconfirm \
    --clean \
    --windowed \
    --name "${APP_NAME}" \
    --distpath dist \
    --workpath build/pyinstaller \
    --paths src \
    --exclude-module PySide6.QtWebEngineCore \
    --exclude-module PySide6.QtWebEngineWidgets \
    --exclude-module PySide6.QtWebEngineQuick \
    --exclude-module PySide6.QtWebChannel \
    --exclude-module PySide6.QtPdf \
    --exclude-module PySide6.QtPdfWidgets \
    --exclude-module PySide6.QtQml \
    --exclude-module PySide6.QtQuick \
    --exclude-module PySide6.QtQuickWidgets \
    --exclude-module PySide6.QtQuick3D \
    --exclude-module PySide6.Qt3DCore \
    --exclude-module PySide6.Qt3DRender \
    --exclude-module PySide6.QtCharts \
    --exclude-module PySide6.QtDataVisualization \
    --exclude-module tkinter \
    packaging/entry.py

echo "==> Assembling AppDir"
APPDIR="build/AppDir"
mkdir -p "${APPDIR}/usr/bin"
cp -r "dist/${APP_NAME}/." "${APPDIR}/usr/bin/"
cp packaging/l4d2-mod-manager.desktop "${APPDIR}/"
cp packaging/icon-256.png "${APPDIR}/${APP_NAME}.png"
cp packaging/icon-256.png "${APPDIR}/.DirIcon"
cp packaging/AppRun "${APPDIR}/AppRun"
chmod +x "${APPDIR}/AppRun" "${APPDIR}/usr/bin/${APP_NAME}"

if [ ! -f "${CACHE}/appimagetool-x86_64.AppImage" ]; then
    echo "==> Downloading appimagetool"
    if command -v curl >/dev/null 2>&1; then
        curl -fL -o "${CACHE}/appimagetool-x86_64.AppImage" "${APPIMAGETOOL_URL}"
    else
        wget -O "${CACHE}/appimagetool-x86_64.AppImage" "${APPIMAGETOOL_URL}"
    fi
    chmod +x "${CACHE}/appimagetool-x86_64.AppImage"
fi

echo "==> Packing AppImage"
"${CACHE}/appimagetool-x86_64.AppImage" --appimage-extract-and-run \
    "${APPDIR}" "${OUT}"

echo "==> Self-test (offscreen, killed by timeout = healthy launch)"
set +e
QT_QPA_PLATFORM=offscreen timeout 8 "${OUT}" --appimage-extract-and-run >/dev/null 2>&1
STATUS=$?
set -e
if [ "${STATUS}" -ne 124 ]; then
    echo "Self-test failed (exit ${STATUS})" >&2
    exit 1
fi
echo "Self-test OK (app stayed running until timeout)"

ls -lh "${OUT}"
echo "==> Done: ${OUT}"
echo "Note: to run without FUSE: ./${OUT##*/} --appimage-extract-and-run"
