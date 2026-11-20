(() => {
  const sidebar = document.querySelector('.sidebar');
  const dialog = document.getElementById('swTabSwitcher');
  if (!sidebar || !dialog || typeof dialog.showModal !== 'function') return;

  const mobile = window.matchMedia('(max-width: 768px)');
  const title = document.getElementById('swTabSwitcherTitle');
  const options = dialog.querySelector('.sw-tab-switcher-options');
  const closeButton = dialog.querySelector('.sw-tab-switcher-close');
  const themeControls = sidebar.querySelector('.sidebar-theme');
  const themeSlot = dialog.querySelector('.sw-tab-switcher-theme-controls');
  const themeHome = themeControls?.parentNode;
  const themeNext = themeControls?.nextSibling;
  const syncThemePosition = () => {
    if (!themeControls || !themeSlot) return;
    if (mobile.matches) themeSlot.append(themeControls);
    else if (themeNext?.parentNode === themeHome) themeHome.insertBefore(themeControls, themeNext);
    else themeHome.append(themeControls);
  };
  syncThemePosition();
  const pageLinks = [...sidebar.querySelectorAll('.nav-icons > a.nav-icon')].filter((link) =>
    ['Dashboard', 'Monthly Analysis', 'Lend Tracker', 'Savings Goals'].includes(link.getAttribute('aria-label'))
  );
  const profileLink = sidebar.querySelector('.avatar-link');

  const labelFor = (link) => link === profileLink ? 'Profile' :
    (link.getAttribute('aria-label') || link.title || 'Page');
  const shortLabelFor = (link) => ({
    Dashboard: 'Home',
    'Monthly Analysis': 'Monthly',
    'Lend Tracker': 'Lend',
    'Savings Goals': 'Savings',
  })[labelFor(link)] || labelFor(link);

  function openSwitcher(source) {
    if (!mobile.matches || dialog.open) return;
    title.textContent = 'Quick switch';
    options.replaceChildren();
    pageLinks.forEach((link) => {
      const option = document.createElement('a');
      option.className = 'sw-tab-switcher-option';
      if (link === source || (!pageLinks.includes(source) && link.classList.contains('active'))) {
        option.classList.add('is-selected');
      }
      if (link.classList.contains('active')) option.setAttribute('aria-current', 'page');
      option.href = link.href;
      option.setAttribute('aria-label', labelFor(link));
      const icon = document.createElement('span');
      icon.className = 'sw-tab-switcher-icon';
      icon.append(link.querySelector('svg').cloneNode(true));
      const text = document.createElement('span');
      text.className = 'sw-tab-switcher-label';
      text.textContent = shortLabelFor(link);
      option.append(icon, text);
      options.append(option);
    });
    dialog.showModal();
    document.body.classList.add('sw-tab-switcher-open');
    closeButton.focus();
  }

  const targets = [...sidebar.querySelectorAll('.avatar-link, .nav-icons .nav-icon'),
    document.querySelector('.mobile-profile-link')].filter(Boolean);
  targets.forEach((target) => {
    let timer = null;
    let startX = 0;
    let startY = 0;
    let suppressClickUntil = 0;
    const cancelTimer = () => {
      window.clearTimeout(timer);
      timer = null;
    };
    target.addEventListener('pointerdown', (event) => {
      if (!mobile.matches || event.button !== 0) return;
      cancelTimer();
      startX = event.clientX;
      startY = event.clientY;
      timer = window.setTimeout(() => {
        suppressClickUntil = Date.now() + 900;
        openSwitcher(target);
      }, 500);
    });
    target.addEventListener('pointermove', (event) => {
      if (Math.hypot(event.clientX - startX, event.clientY - startY) > 12) cancelTimer();
    });
    ['pointerup', 'pointercancel', 'pointerleave'].forEach((eventName) => {
      target.addEventListener(eventName, cancelTimer);
    });
    target.addEventListener('click', (event) => {
      if (Date.now() < suppressClickUntil) {
        event.preventDefault();
        event.stopImmediatePropagation();
      }
    }, true);
    target.addEventListener('contextmenu', (event) => {
      if (!mobile.matches) return;
      event.preventDefault();
      suppressClickUntil = Date.now() + 900;
      openSwitcher(target);
    });
  });

  const closeSwitcher = () => {
    if (!dialog.open) return false;
    dialog.close();
    return true;
  };
  window.spendwiseCloseTabSwitcher = closeSwitcher;
  closeButton.addEventListener('click', closeSwitcher);
  dialog.addEventListener('click', (event) => {
    if (event.target === dialog) closeSwitcher();
  });
  dialog.addEventListener('close', () => document.body.classList.remove('sw-tab-switcher-open'));
  mobile.addEventListener('change', () => {
    if (!mobile.matches) closeSwitcher();
    syncThemePosition();
  });
})();
