(() => {
  const authFormSelector = '.auth-form';

  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Enter') return;
    const input = e.target;
    if (!input?.matches?.('.field-input')) return;

    const form = input.closest(authFormSelector);
    if (!form) return;

    const inputs = Array.from(form.querySelectorAll('.field-input'));
    const idx = inputs.indexOf(input);
    if (idx === -1) return;

    e.preventDefault();

    if (idx < inputs.length - 1) {
      inputs[idx + 1].focus();
    } else {
      form.requestSubmit();
    }
  });
})();
