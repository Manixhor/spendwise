/**
 * SpendWise Currency Sync
 * Reads currency from localStorage and updates all [data-curr] elements on load.
 * Also reformats elements with [data-amount] using the correct currency.
 * Exposes window.setSpendWiseCurrency(code) to update everywhere.
 */
(() => {
  const STORAGE_KEY = 'spendwise-currency';
  const SYMBOLS = { inr: '₹', usd: '$' };
  const LOCALES = { inr: 'en-IN', usd: 'en-US' };

  function getStoredCurrency() {
    try { return localStorage.getItem(STORAGE_KEY) || 'inr'; }
    catch { return 'inr'; }
  }

  function storeCurrency(code) {
    try { localStorage.setItem(STORAGE_KEY, code); } catch {}
  }

  /** Format a raw number with the given currency code */
  function formatAmount(value, code) {
    const sym = SYMBOLS[code] || '₹';
    const loc = LOCALES[code] || 'en-IN';
    const num = Number(value || 0);
    const isNeg = num < 0;
    const abs = Math.abs(num);
    const formatted = abs.toLocaleString(loc, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    if (isNeg) return `−${sym}${formatted}`;
    return `${sym}${formatted}`;
  }

  /** Apply symbol to every [data-curr] element and reformat [data-amount] elements */
  function applyCurrency(code) {
    const sym = SYMBOLS[code] || '₹';

    // Update simple symbol tags
    document.querySelectorAll('[data-curr]').forEach(el => {
      // If element also has data-amount, reformat the whole text
      if (el.dataset.amount !== undefined) {
        el.textContent = formatAmount(el.dataset.amount, code);
      } else {
        el.textContent = sym;
      }
    });

    // Update any standalone data-amount elements (without data-curr)
    document.querySelectorAll('[data-amount]:not([data-curr])').forEach(el => {
      el.textContent = formatAmount(el.dataset.amount, code);
    });
  }

  /** Update the global USER_CURRENCY var used by dashboard/monthly JS formatters */
  function updateGlobalVars(code) {
    const sym = SYMBOLS[code] || '₹';
    const loc = LOCALES[code] || 'en-IN';
    if (typeof window.USER_CURRENCY !== 'undefined') window.USER_CURRENCY = code;
    if (typeof window.CURRENCY_SYMBOLS_JS !== 'undefined') {
      window.CURRENCY_SYMBOLS_JS[code] = sym;
    }
    if (typeof window.CURRENCY_LOCALES_JS !== 'undefined') {
      window.CURRENCY_LOCALES_JS[code] = loc;
    }
    // Update expense chatbot currency element
    const chatbotCurr = document.getElementById('expenseChatbotCurrency');
    if (chatbotCurr) chatbotCurr.textContent = sym;
  }

  /** Main function — call from any page to switch currency everywhere */
  window.setSpendWiseCurrency = function (code) {
    if (!code || !SYMBOLS[code]) return;
    storeCurrency(code);
    applyCurrency(code);
    updateGlobalVars(code);
  };

  /** Format a number with the stored currency */
  window.formatStoredCurrency = function (value, opts = {}) {
    const code = getStoredCurrency();
    const sym = SYMBOLS[code] || '₹';
    const loc = LOCALES[code] || 'en-IN';
    const num = Number(value || 0);
    const prefix = num < 0 ? '−' : (opts.showPlus && num > 0 ? '+' : '');
    return `${prefix}${sym}${Math.abs(num).toLocaleString(loc, {
      minimumFractionDigits: opts.decimals ?? 2,
      maximumFractionDigits: opts.decimals ?? 2,
    })}`;
  };

  /** On DOM ready, sync all currency elements from localStorage */
  function syncOnLoad() {
    const code = getStoredCurrency();
    applyCurrency(code);
    updateGlobalVars(code);
    // Sync the profile currency picker active state
    const picker = document.getElementById('currencyPicker');
    if (picker) {
      picker.querySelectorAll('.pf-currency-card').forEach(c => {
        c.classList.toggle('is-active', c.dataset.currency === code);
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', syncOnLoad);
  } else {
    syncOnLoad();
  }
})();
