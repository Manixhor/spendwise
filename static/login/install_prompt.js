(() => {
  const DISMISS_KEY = 'spendwise-dashboard-install-v2-dismissed-until';
  const DISMISS_MS = 30 * 24 * 60 * 60 * 1000;
  const isInstalled = () => window.matchMedia('(display-mode: standalone)').matches ||
    window.navigator.standalone === true;
  const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) ||
    (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  let installEvent = null;
  let backdrop = null;

  function dismissed() {
    try { return Number(localStorage.getItem(DISMISS_KEY)) > Date.now(); }
    catch (_) { return false; }
  }

  function close(remember = false) {
    backdrop?.remove();
    backdrop = null;
    if (remember) {
      try { localStorage.setItem(DISMISS_KEY, String(Date.now() + DISMISS_MS)); }
      catch (_) { /* Storage may be disabled. */ }
    }
  }

  function instructions() {
    const text = backdrop?.querySelector('.install-prompt__description');
    const button = backdrop?.querySelector('.install-prompt__install');
    if (!text || !button) return;
    text.textContent = isIOS
      ? 'In Safari, tap Share, then Add to Home Screen, then Add.'
      : 'Open your browser menu and choose Install app or Add to Home screen.';
    button.textContent = 'Got it';
    button.dataset.showingInstructions = 'true';
  }

  async function proceed() {
    if (backdrop?.querySelector('.install-prompt__install')?.dataset.showingInstructions) {
      close(true);
      return;
    }
    if (!installEvent) {
      instructions();
      return;
    }
    const event = installEvent;
    installEvent = null;
    close();
    try {
      await event.prompt();
      const choice = await event.userChoice;
      if (choice?.outcome === 'accepted' || choice?.outcome === 'dismissed') close(true);
    } catch (_) {
      show();
      instructions();
    }
  }

  function show() {
    if (backdrop || dismissed() || isInstalled() || !document.body) return;

    backdrop = document.createElement('div');
    backdrop.className = 'install-prompt-backdrop';
    const panel = document.createElement('div');
    panel.className = 'install-prompt';
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-modal', 'true');
    panel.setAttribute('aria-labelledby', 'install-prompt-title');
    const iconUrl = document.querySelector('link[rel="apple-touch-icon"]')?.href;
    if (iconUrl) {
      const icon = document.createElement('img');
      icon.className = 'install-prompt__icon';
      icon.src = iconUrl;
      icon.alt = '';
      panel.append(icon);
    }
    const title = document.createElement('h2');
    title.id = 'install-prompt-title';
    title.textContent = 'Add SpendWise to your home screen?';
    const detail = document.createElement('p');
    detail.className = 'install-prompt__description';
    detail.textContent = installEvent
      ? 'Open SpendWise like an app whenever you need it.'
      : 'See how to add SpendWise to your home screen.';
    const actions = document.createElement('div');
    actions.className = 'install-prompt__actions';
    const install = document.createElement('button');
    install.type = 'button';
    install.className = 'install-prompt__install';
    install.textContent = installEvent ? 'OK, add web app' : 'Show install steps';
    install.addEventListener('click', proceed);
    const later = document.createElement('button');
    later.type = 'button';
    later.className = 'install-prompt__later';
    later.textContent = 'Not now';
    later.addEventListener('click', () => close(true));
    const closeButton = document.createElement('button');
    closeButton.type = 'button';
    closeButton.className = 'install-prompt__close';
    closeButton.setAttribute('aria-label', 'Dismiss install suggestion');
    closeButton.textContent = '\u00d7';
    closeButton.addEventListener('click', () => close(true));
    actions.append(install, later);
    panel.append(title, detail, actions, closeButton);
    backdrop.append(panel);
    document.body.append(backdrop);
    install.focus();
  }

  window.addEventListener('beforeinstallprompt', (event) => {
    event.preventDefault();
    installEvent = event;
    const button = backdrop?.querySelector('.install-prompt__install');
    if (button) {
      delete button.dataset.showingInstructions;
      button.textContent = 'OK, add web app';
    }
    const detail = backdrop?.querySelector('.install-prompt__description');
    if (detail) {
      detail.textContent = 'Open SpendWise like an app whenever you need it.';
    }
    show();
  });
  window.addEventListener('appinstalled', () => {
    installEvent = null;
    close(true);
  });
  document.addEventListener('DOMContentLoaded', show);
  if (document.readyState !== 'loading') show();
})();
