#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
JAVA_HOME="${JAVA_HOME:?Set JAVA_HOME to JDK 17}"
KEY="$ROOT/.signing/upload-key.p12"
PASSWORD_FILE="$ROOT/.signing/password"
INPUT="$ROOT/app/build/outputs/bundle/release/app-release.aab"
OUTPUT="$ROOT/build/Spendwise.aab"
test -f "$KEY" && test -f "$PASSWORD_FILE" && test -f "$INPUT"
mkdir -p "$ROOT/build"
"$JAVA_HOME/bin/jarsigner" -keystore "$KEY" -storetype PKCS12 \
  -storepass "$(cat "$PASSWORD_FILE")" -signedjar "$OUTPUT" "$INPUT" spendwise-upload
"$JAVA_HOME/bin/jarsigner" -verify "$OUTPUT"
