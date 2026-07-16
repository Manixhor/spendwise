(() => {
  const focusableSelector = [
    'input:not([type="hidden"]):not([type="file"]):not([type="checkbox"]):not([type="radio"])',
    'textarea',
    'select',
  ].join(',');

  const getViewport = () => window.visualViewport || null;

  const syncKeyboardState = () => {
    const viewport = getViewport();
    const layoutHeight = Math.max(
      document.documentElement.clientHeight || 0,
      window.innerHeight || 0,
    );
    const visualHeight = viewport ? viewport.height : window.innerHeight;
    const viewportTop = viewport ? viewport.offsetTop : 0;
    const keyboardHeight = viewport
      ? Math.max(0, layoutHeight - viewport.height - viewport.offsetTop)
      : 0;
    const keyboardOpen = keyboardHeight > 120;
    const activeModal = document.querySelector('.modal-overlay.active, .export-modal.show, .expense-chatbot-panel.is-open');

    document.documentElement.style.setProperty('--app-visual-height', `${visualHeight}px`);
    document.documentElement.style.setProperty('--app-viewport-top', `${viewportTop}px`);
    document.documentElement.style.setProperty('--app-keyboard-height', `${keyboardHeight}px`);
    document.documentElement.style.setProperty('--app-keyboard-shift', `${keyboardOpen ? Math.round(keyboardHeight * 0.5) : 0}px`);
    document.body.classList.toggle('ios-keyboard-open', keyboardOpen);
    document.body.classList.toggle('ios-modal-keyboard-open', keyboardOpen && Boolean(activeModal));
  };

  const keepFocusedFieldVisible = (target) => {
    if (!target?.matches?.(focusableSelector)) return;

    window.setTimeout(() => {
      syncKeyboardState();
      const container = target.closest('.modal-card, .export-modal__card, .expense-chatbot-panel, .card, form') || target;
      target.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'smooth' });
      if (container !== target && container.scrollIntoView) {
        container.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'smooth' });
      }
    }, 120);
  };

  window.visualViewport?.addEventListener('resize', syncKeyboardState);
  window.visualViewport?.addEventListener('scroll', syncKeyboardState);
  window.addEventListener('resize', syncKeyboardState);
  window.addEventListener('orientationchange', () => window.setTimeout(syncKeyboardState, 250));

  document.addEventListener('focusin', (event) => {
    if (!event.target.matches?.(focusableSelector)) return;
    document.body.classList.add('ios-input-focused');
    syncKeyboardState();
    keepFocusedFieldVisible(event.target);
  });

  document.addEventListener('focusout', () => {
    window.setTimeout(() => {
      if (!document.activeElement?.matches?.(focusableSelector)) {
        document.body.classList.remove('ios-input-focused', 'ios-keyboard-open', 'ios-modal-keyboard-open');
      }
      syncKeyboardState();
    }, 180);
  });

  document.addEventListener('click', () => window.setTimeout(syncKeyboardState, 0), true);
  syncKeyboardState();
})();
