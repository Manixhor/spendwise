#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
SDK="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
TOOLS="$SDK/build-tools/36.0.0"
PLATFORM="$SDK/platforms/android-36/android.jar"
JAVA_HOME="${JAVA_HOME:?Set JAVA_HOME to JDK 17}"
OUT="$ROOT/build/manual"
mkdir -p "$OUT/compiled" "$OUT/classes" "$OUT/dex"

"$TOOLS/aapt2" compile "$ROOT/app/src/main/res/drawable/app_icon.png" -o "$OUT/compiled"
"$TOOLS/aapt2" link -I "$PLATFORM" --manifest "$ROOT/app/src/main/AndroidManifest.xml" \
  --auto-add-overlay -o "$OUT/unsigned.apk" "$OUT/compiled/drawable_app_icon.png.flat"
"$JAVA_HOME/bin/javac" -source 8 -target 8 -cp "$PLATFORM" -d "$OUT/classes" \
  "$ROOT/app/src/main/java/com/manixhor/spendwise/MainActivity.java"
"$TOOLS/d8" --lib "$PLATFORM" --output "$OUT/dex" \
  "$OUT"/classes/com/manixhor/spendwise/*.class
cp "$OUT/unsigned.apk" "$OUT/with-dex.apk"
(cd "$OUT/dex" && zip -q -j "$OUT/with-dex.apk" classes.dex)
"$TOOLS/zipalign" -p -f 4 "$OUT/with-dex.apk" "$OUT/aligned.apk"

SIGNING_DIR="$ROOT/.signing"
if [ ! -f "$SIGNING_DIR/upload-key.p12" ] || [ ! -f "$SIGNING_DIR/password" ]; then
  echo "Missing signing key in android/.signing/" >&2
  exit 1
fi
SIGNING_PASSWORD=$(cat "$SIGNING_DIR/password")
"$TOOLS/apksigner" sign --ks "$SIGNING_DIR/upload-key.p12" --ks-type PKCS12 \
  --ks-key-alias spendwise-upload --ks-pass "pass:$SIGNING_PASSWORD" \
  --out "$ROOT/build/Spendwise.apk" "$OUT/aligned.apk"
"$TOOLS/apksigner" verify --verbose "$ROOT/build/Spendwise.apk"
