package com.manixhor.spendwise;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.app.DownloadManager;
import android.app.NotificationManager;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.provider.Settings;
import android.webkit.CookieManager;
import android.webkit.URLUtil;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceError;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import org.json.JSONTokener;

public class MainActivity extends Activity {
    private static final String HOME = "https://site--spendwise--m9lhjm5ftxzt.code.run/";
    private static final String HOST = "site--spendwise--m9lhjm5ftxzt.code.run";
    private static final int FILE_REQUEST = 1001;
    private WebView webView;
    private ValueCallback<Uri[]> fileCallback;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        webView = new WebView(this);
        webView.getSettings().setJavaScriptEnabled(true);
        webView.getSettings().setDomStorageEnabled(true);
        webView.getSettings().setAllowFileAccess(false);
        webView.getSettings().setAllowContentAccess(true);
        webView.getSettings().setAllowFileAccessFromFileURLs(false);
        webView.getSettings().setAllowUniversalAccessFromFileURLs(false);
        webView.getSettings().setMixedContentMode(android.webkit.WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        webView.getSettings().setUserAgentString(webView.getSettings().getUserAgentString() + " SpendwiseAndroid/4");
        CookieManager.getInstance().setAcceptCookie(true);
        webView.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                if ("https".equals(uri.getScheme()) && HOST.equals(uri.getHost())) return false;
                if (!("https".equals(uri.getScheme()) || "http".equals(uri.getScheme()) || "mailto".equals(uri.getScheme()) || "tel".equals(uri.getScheme()))) return true;
                try { startActivity(new Intent(Intent.ACTION_VIEW, uri)); } catch (Exception ignored) { }
                return true;
            }
            @Override public void onPageFinished(WebView view, String url) {
                CookieManager.getInstance().flush();
                Uri uri = Uri.parse(url);
                if (!HOST.equals(uri.getHost())) return;
                String path = uri.getPath();
                if ("/login/".equals(path) || "/logout/".equals(path)) {
                    AllowanceReminderReceiver.clearAllowance(MainActivity.this);
                } else if ("/dashboard/".equals(path)) {
                    view.evaluateJavascript("(function(){var e=document.querySelector('.spending-check-amount [data-curr]');return e?e.textContent.trim():''})()", value -> {
                        try {
                            Object parsed = new JSONTokener(value).nextValue();
                            String amount = parsed instanceof String ? (String) parsed : "";
                            if (amount.matches("[₹$][0-9,]+(\\.[0-9]{1,2})?")) {
                                AllowanceReminderReceiver.updateAllowance(MainActivity.this, amount);
                            } else {
                                AllowanceReminderReceiver.clearAllowance(MainActivity.this);
                            }
                        } catch (Exception ignored) {
                            AllowanceReminderReceiver.clearAllowance(MainActivity.this);
                        }
                    });
                }
            }
            @Override public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request.isForMainFrame()) {
                    Toast.makeText(MainActivity.this, "Could not load SpendWise. Check your connection and try again.", Toast.LENGTH_LONG).show();
                }
            }
        });
        webView.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (fileCallback != null) fileCallback.onReceiveValue(null);
                fileCallback = callback;
                try { startActivityForResult(params.createIntent(), FILE_REQUEST); return true; }
                catch (Exception ex) { fileCallback = null; return false; }
            }
        });
        webView.setDownloadListener((url, agent, disposition, mime, length) -> {
            Uri uri = Uri.parse(url);
            if (!"https".equals(uri.getScheme()) || !HOST.equals(uri.getHost())) {
                try { startActivity(new Intent(Intent.ACTION_VIEW, uri)); } catch (Exception ignored) { }
                return;
            }
            String fileName = URLUtil.guessFileName(url, disposition, mime).replaceAll("[^A-Za-z0-9._-]", "_");
            DownloadManager.Request download = new DownloadManager.Request(uri);
            download.setTitle(fileName);
            download.setMimeType(mime);
            download.addRequestHeader("User-Agent", agent);
            String cookie = CookieManager.getInstance().getCookie(url);
            if (cookie != null) download.addRequestHeader("Cookie", cookie);
            download.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
            download.setDestinationInExternalFilesDir(this, Environment.DIRECTORY_DOWNLOADS, fileName);
            try {
                ((DownloadManager) getSystemService(Context.DOWNLOAD_SERVICE)).enqueue(download);
                Toast.makeText(this, "Download started", Toast.LENGTH_SHORT).show();
            } catch (Exception ex) {
                Toast.makeText(this, "Download failed", Toast.LENGTH_LONG).show();
            }
        });
        setContentView(webView);
        webView.loadUrl(HOME);
        promptForNotifications();
    }

    private void promptForNotifications() {
        NotificationManager manager = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
        boolean granted = manager != null && manager.areNotificationsEnabled()
                && (Build.VERSION.SDK_INT < 33 ||
                checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED);
        if (granted || getPreferences(MODE_PRIVATE).getBoolean("notification_prompt_requested", false)) return;
        new AlertDialog.Builder(this)
                .setTitle("Enable SpendWise notifications?")
                .setMessage("Get a daily reminder of your saved spending allowance. You can change this later in Android Settings.")
                .setPositiveButton("Enable notifications", (dialog, which) -> {
                    getPreferences(MODE_PRIVATE).edit().putBoolean("notification_prompt_requested", true).apply();
                    if (Build.VERSION.SDK_INT >= 33 &&
                            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                        requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, 1002);
                    } else {
                        Intent settings = new Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS)
                                .putExtra(Settings.EXTRA_APP_PACKAGE, getPackageName());
                        startActivity(settings);
                    }
                })
                .setNegativeButton("Later", (dialog, which) ->
                        getPreferences(MODE_PRIVATE).edit().putBoolean("notification_prompt_requested", true).apply())
                .show();
    }

    @Override protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (request == FILE_REQUEST && fileCallback != null) {
            fileCallback.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(result, data));
            fileCallback = null;
        }
    }

    @Override public void onBackPressed() {
        if (webView != null && webView.canGoBack()) webView.goBack();
        else super.onBackPressed();
    }

    @Override protected void onDestroy() {
        if (fileCallback != null) fileCallback.onReceiveValue(null);
        if (webView != null) webView.destroy();
        super.onDestroy();
    }
}
