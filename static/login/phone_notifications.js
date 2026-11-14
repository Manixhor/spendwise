(() => {
  const enable = document.getElementById('enablePhoneNotifications');
  const disable = document.getElementById('disablePhoneNotifications');
  const status = document.getElementById('phoneNotificationStatus');
  if (!enable || !disable || !status) return;
  const supported = 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
  const csrf = document.cookie.split('; ').find(item => item.startsWith('csrftoken='))?.split('=').slice(1).join('') || '';
  const keyBytes = (value) => {
    const padded = (value + '='.repeat((4 - value.length % 4) % 4)).replace(/-/g, '+').replace(/_/g, '/');
    return Uint8Array.from(atob(padded), char => char.charCodeAt(0));
  };
  const refresh = async () => {
    if (!supported) {
      enable.disabled = true;
      status.textContent = 'Phone notifications are unavailable in this browser.';
      return;
    }
    const registration = await navigator.serviceWorker.ready;
    const subscription = await registration.pushManager.getSubscription();
    enable.hidden = !!subscription;
    disable.hidden = !subscription;
    status.textContent = subscription ? 'Notifications are on for this phone.' : '';
  };
  enable.addEventListener('click', async () => {
    enable.disabled = true;
    try {
      const permission = await Notification.requestPermission();
      if (permission !== 'granted') throw new Error('Notification permission was not allowed.');
      const keyResponse = await fetch('/api/push/key/');
      if (!keyResponse.ok) throw new Error('Could not enable notifications.');
      const { publicKey } = await keyResponse.json();
      const registration = await navigator.serviceWorker.ready;
      const subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true, applicationServerKey: keyBytes(publicKey),
      });
      const response = await fetch('/api/push/subscribe/', {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
        body: JSON.stringify(subscription.toJSON()),
      });
      if (!response.ok) {
        await subscription.unsubscribe();
        throw new Error('Could not save this phone. Please try again.');
      }
      await refresh();
    } catch (error) {
      status.textContent = error.message || 'Could not enable notifications.';
    } finally { enable.disabled = false; }
  });
  disable.addEventListener('click', async () => {
    const registration = await navigator.serviceWorker.ready;
    const subscription = await registration.pushManager.getSubscription();
    if (subscription) {
      await fetch('/api/push/unsubscribe/', {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
        body: JSON.stringify({ endpoint: subscription.endpoint }),
      });
      await subscription.unsubscribe();
    }
    await refresh();
  });
  refresh().catch(() => { status.textContent = 'Could not check notification status.'; });
})();
