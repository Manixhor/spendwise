(() => {
  const ua = navigator.userAgent || '';
  const match = ua.match(/SpendwiseAndroid\/(\d+)/i);
  if (!match && !/; wv\)/i.test(ua)) return;
  const installedVersion = match ? Number(match[1]) : 1;

  async function checkForUpdate() {
    let latest;
    try {
      const response = await fetch('/android/latest.json', { cache: 'no-store', credentials: 'same-origin' });
      if (!response.ok) return;
      latest = await response.json();
    } catch (_) { return; }
    if (!Number.isInteger(latest.version_code) || latest.version_code <= installedVersion) return;
    if (sessionStorage.getItem('spendwise-update-dismissed') === String(latest.version_code)) return;

    const notice = document.createElement('aside');
    notice.setAttribute('role', 'status');
    notice.setAttribute('aria-label', 'Spendwise app update');
    notice.style.cssText = 'position:fixed;left:16px;right:16px;bottom:82px;z-index:9999;padding:16px;border-radius:14px;background:#172036;color:#fff;box-shadow:0 8px 30px #0005;font:15px/1.4 system-ui,sans-serif';
    const message = document.createElement('div');
    message.textContent = `Spendwise ${latest.version_name || ''} is available. Install it over this app to keep your data.`;
    const actions = document.createElement('div');
    actions.style.cssText = 'display:flex;gap:14px;margin-top:12px;align-items:center';
    const link = document.createElement('a');
    link.href = latest.download_url || '/download/android/';
    link.textContent = 'Get update';
    link.style.cssText = 'color:#75e2c0;font-weight:700';
    const later = document.createElement('button');
    later.type = 'button';
    later.textContent = 'Later';
    later.style.cssText = 'border:0;background:transparent;color:#fff;padding:0;font:inherit';
    later.addEventListener('click', () => {
      sessionStorage.setItem('spendwise-update-dismissed', String(latest.version_code));
      notice.remove();
    });
    actions.append(link, later);
    notice.append(message, actions);
    document.body.append(notice);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', checkForUpdate);
  else checkForUpdate();
})();
