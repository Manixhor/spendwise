package com.manixhor.spendwise;

import android.Manifest;
import android.app.AlarmManager;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.os.Build;

import java.util.Calendar;

public class AllowanceReminderReceiver extends BroadcastReceiver {
    private static final String CHANNEL = "spendwise_daily_allowance";
    private static final String ACTION_REMIND = "com.manixhor.spendwise.DAILY_ALLOWANCE";
    private static final String PREFS = "spendwise_reminders";
    private static final String AMOUNT = "allowance_amount";

    static void updateAllowance(Context context, String amount) {
        if (amount == null || amount.length() > 32 || amount.isEmpty()) return;
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putString(AMOUNT, amount).apply();
        schedule(context);
    }

    static void clearAllowance(Context context) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().remove(AMOUNT).apply();
        AlarmManager alarm = (AlarmManager) context.getSystemService(Context.ALARM_SERVICE);
        if (alarm != null) alarm.cancel(pending(context));
    }

    private static PendingIntent pending(Context context) {
        Intent intent = new Intent(context, AllowanceReminderReceiver.class).setAction(ACTION_REMIND);
        return PendingIntent.getBroadcast(context, 4, intent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }

    static void schedule(Context context) {
        SharedPreferences preferences = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        if (!preferences.contains(AMOUNT)) return;
        Calendar next = Calendar.getInstance();
        next.set(Calendar.HOUR_OF_DAY, 8);
        next.set(Calendar.MINUTE, 0);
        next.set(Calendar.SECOND, 0);
        next.set(Calendar.MILLISECOND, 0);
        if (next.getTimeInMillis() <= System.currentTimeMillis()) next.add(Calendar.DAY_OF_YEAR, 1);
        AlarmManager alarm = (AlarmManager) context.getSystemService(Context.ALARM_SERVICE);
        if (alarm != null) alarm.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, next.getTimeInMillis(), pending(context));
    }

    @Override public void onReceive(Context context, Intent intent) {
        if (Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction())) {
            schedule(context);
            return;
        }
        if (!ACTION_REMIND.equals(intent.getAction())) return;
        String amount = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(AMOUNT, null);
        if (amount == null) return;
        boolean permitted = Build.VERSION.SDK_INT < 33 ||
                context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED;
        if (permitted) {
            NotificationManager manager = (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
            if (manager != null && manager.areNotificationsEnabled()) {
                manager.createNotificationChannel(new NotificationChannel(CHANNEL,
                        "Daily allowance", NotificationManager.IMPORTANCE_DEFAULT));
                PendingIntent open = PendingIntent.getActivity(context, 5,
                        new Intent(context, MainActivity.class),
                        PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
                Notification notice = new Notification.Builder(context, CHANNEL)
                        .setSmallIcon(context.getApplicationInfo().icon)
                        .setContentTitle("Your daily allowance")
                        .setContentText(amount + " available for today")
                        .setContentIntent(open)
                        .setAutoCancel(true)
                        .build();
                manager.notify(8, notice);
            }
        }
        schedule(context);
    }
}
