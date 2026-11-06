# Spendwise Android

Android WebView shell for the hosted Spendwise service. The configured site is the same host used by the iOS app. Before publishing, verify that the host is stable, publicly reachable, and controlled by the Spendwise owner.

Build with JDK 17, Android SDK 36, Gradle 8.13 and Android Gradle Plugin 8.12.1:

```sh
gradle -p android :app:assembleRelease :app:bundleRelease
```

The Gradle release bundle is unsigned by default. Run `sign-bundle.sh` to sign it with the private upload key before uploading to Play Console. `build-apk.sh` creates a signed direct-download APK using the same key in `android/.signing/` (ignored by Git). Back up that key and its password securely; future APK updates must use the same key. This shell depends on Android System WebView and does not yet provide native push notification support; test every advertised feature before release.

For each Android update, increase `versionCode` and `versionName` in both `app/build.gradle` and `app/src/main/AndroidManifest.xml`, build and sign the APK with the same key, replace `static/downloads/Spendwise.apk`, and update `/android/latest.json` in `login/views.py`. The website shows an update notice inside older Android WebView apps. Android requires the person to approve the download and installation; direct website and GitHub downloads cannot silently update apps. Publishing through Google Play enables managed updates.
