#!/bin/sh
echo start building
source test/bin/activate
pip3 install -r requirements.txt

PROJECT_NAME="fps"

CCACHE_FLAG=""
if ! command -v ccache >/dev/null 2>&1; then
  CCACHE_FLAG="--disable-ccache"
fi

python -m nuitka --mode=standalone $CCACHE_FLAG \
  --static-libpython=no \
  --enable-plugin=pyside6 \
  --include-package-data=easyocr \
  --include-package-data=esptool \
  --windows-console-mode=disable \
  --include-data-dir=assets=assets \
  main.py