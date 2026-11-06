(() => {
  const passwordFields = new Set();

  document.querySelectorAll('.su-toggle-pw[data-target]').forEach((button) => {
    const input = document.getElementById(button.dataset.target);
    if (!input) return;
    passwordFields.add(input);

    button.addEventListener('mousedown', (event) => {
      if (document.activeElement === input) event.preventDefault();
    });

    button.addEventListener('click', () => {
      const reveal = input.type === 'password';
      const start = input.selectionStart;
      const end = input.selectionEnd;
      input.type = reveal ? 'text' : 'password';
      if (document.activeElement === input && start !== null) {
        input.setSelectionRange(start, end);
      }
      button.setAttribute('aria-label', reveal ? 'Hide password' : 'Show password');
      button.querySelector('.eye-open').style.display = reveal ? 'none' : 'block';
      button.querySelector('.eye-closed').style.display = reveal ? 'block' : 'none';
    });
  });

  const viewport = window.visualViewport;
  viewport?.addEventListener('resize', () => {
    const input = document.activeElement;
    if (!passwordFields.has(input)) return;
    const row = input.closest('.field-group');
    if (row.getBoundingClientRect().bottom > viewport.offsetTop + viewport.height) {
      row.scrollIntoView({ block: 'center' });
    }
  });
})();
