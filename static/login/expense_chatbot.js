(() => {
  const root = document.getElementById('expenseChatbot');
  if (!root || root.dataset.ready === 'true') return;
  root.dataset.ready = 'true';

  const hint = document.getElementById('expenseChatbotHint');
  const fab = document.getElementById('expenseChatbotFab');
  const panel = document.getElementById('expenseChatbotPanel');
  const backdrop = document.getElementById('expenseChatbotBackdrop');
  const closeButton = document.getElementById('expenseChatbotClose');
  const messages = document.getElementById('expenseChatbotMessages');
  const suggestions = document.getElementById('expenseChatbotSuggestions');
  const form = document.getElementById('expenseChatbotForm');
  const input = document.getElementById('expenseChatbotInput');
  const sendButton = document.getElementById('expenseChatbotSend');
  const currency = document.getElementById('expenseChatbotCurrency');
  const CURR_SYMBOL = currency?.textContent?.trim() || '₹';
  const CURR_LOCALE = CURR_SYMBOL === '$' ? 'en-US' : 'en-IN';
  const orb = document.getElementById('expenseChatbotOrb');

  let step = 'amount';
  let pendingAmount = 0;
  let warnedAmount = 0;
  let pendingTitle = '';
  let pendingTransaction = null;
  let addedExpense = false;
  let isSaving = false;
  let closeTimer = null;
  let finishTimer = null;
  let inputBlurTimer = null;
  let hintTimer = null;
  let swipeStart = null;
  const aiHistory = [];

  const settleKeyboardLayout = () => {
    syncVisualViewport();
    window.setTimeout(syncVisualViewport, 80);
    window.setTimeout(syncVisualViewport, 180);
    window.setTimeout(syncVisualViewport, 360);
  };

  const focusInputNow = () => {
    if (panel.hidden || input.disabled) return;
    input.focus({ preventScroll: true });
    settleKeyboardLayout();
  };

  const dismissHint = () => {
    window.clearTimeout(hintTimer);
    if (!hint) return;
    hint.classList.remove('is-visible');
    window.setTimeout(() => {
      hint.hidden = true;
    }, 220);
  };

  const syncVisualViewport = () => {
    if (!window.visualViewport) return;
    const viewport = window.visualViewport;
    const layoutHeight = Math.max(
      document.documentElement.clientHeight,
      window.innerHeight || 0,
    );
    const keyboardOffset = Math.max(
      0,
      layoutHeight - viewport.height - viewport.offsetTop,
    );
    root.style.setProperty('--chat-visual-height', `${viewport.height}px`);
    root.style.setProperty('--chat-viewport-top', `${viewport.offsetTop}px`);
    root.style.setProperty('--chat-keyboard-offset', `${keyboardOffset}px`);
    root.style.setProperty('--chat-bottom-offset', '0px');
    document.documentElement.style.setProperty('--app-visual-height', `${viewport.height}px`);
    document.documentElement.style.setProperty('--app-keyboard-offset', `${keyboardOffset}px`);
    document.documentElement.style.setProperty('--app-keyboard-height', `${keyboardOffset}px`);
    document.documentElement.style.setProperty('--sw-visible-height', `${viewport.height}px`);
    document.documentElement.style.setProperty('--sw-keyboard-height', `${keyboardOffset}px`);
    document.body.classList.toggle(
      'expense-chatbot-keyboard-open',
      !panel.hidden && keyboardOffset > 120,
    );
    if (!panel.hidden && keyboardOffset > 120) {
      window.requestAnimationFrame(() => {
        messages.scrollTop = messages.scrollHeight;
      });
    }
  };

  const localDate = () => {
    const now = new Date();
    const offset = now.getTimezoneOffset() * 60000;
    return new Date(now.getTime() - offset).toISOString().slice(0, 10);
  };

  const csrfToken = () => {
    const token = document.cookie.split('; ')
      .find((item) => item.startsWith('csrftoken='));
    return token ? decodeURIComponent(token.split('=').slice(1).join('=')) : '';
  };

  const addMessage = (text, sender = 'assistant') => {
    const bubble = document.createElement('div');
    bubble.className = `expense-chatbot-message is-${sender}`;
    bubble.textContent = text;
    messages.appendChild(bubble);
    messages.scrollTop = messages.scrollHeight;
  };

  const showSuggestions = (items = []) => {
    suggestions.replaceChildren();
    items.forEach(({ label, action }) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = label;
      button.addEventListener('click', action);
      suggestions.appendChild(button);
    });
  };

  const inferCategory = (title) => {
    const value = title.toLowerCase();
    const groups = [
      ['food', ['food', 'lunch', 'dinner', 'breakfast', 'coffee', 'tea', 'snack', 'restaurant']],
      ['transport', ['cab', 'uber', 'ola', 'bus', 'train', 'fuel', 'petrol', 'metro']],
      ['groceries', ['grocery', 'groceries', 'vegetable', 'milk', 'supermarket']],
      ['shopping', ['shopping', 'clothes', 'shoes', 'amazon', 'flipkart']],
      ['utilities', ['bill', 'electricity', 'wifi', 'internet', 'recharge', 'gas']],
      ['health', ['doctor', 'medicine', 'medical', 'hospital', 'pharmacy']],
      ['entertainment', ['movie', 'game', 'netflix', 'spotify', 'concert']],
      ['rent', ['rent']],
    ];
    return groups.find(([, words]) => words.some((word) => value.includes(word)))?.[0] || 'other';
  };

  const money = (value) => `${CURR_SYMBOL}${Number(value).toLocaleString(CURR_LOCALE, {maximumFractionDigits: 2})}`;
  const context = async () => {
    const response = await fetch('/api/chatbot/tools/');
    if (!response.ok) throw new Error('Your information is unavailable right now.');
    return response.json();
  };
  const mainSuggestions = () => {
    step = 'amount';
    pendingAmount = 0;
    pendingTitle = '';
    pendingTransaction = null;
    input.value = '';
    input.inputMode = 'text';
    input.placeholder = 'Ask or enter an expense';
    currency.hidden = true;
    showSuggestions([
      {label: 'Can I spend today?', action: () => checkAllowance()},
      {label: 'What’s due next?', action: showBills},
      {label: 'Fix a category', action: () => startCategoryCorrection()},
      {label: '+ Add expense', action: resetForAnother},
    ]);
  };
  const checkAllowance = async (proposed = 0) => {
    try {
      const data = await context();
      if (!data.allowance) {
        addMessage(data.salary_set ? 'Please set your daily allowance in Account, and I can check this for you.' : 'Please set your salary and daily allowance in Account, and I can check this for you.');
        showSuggestions([{label: 'Open Account', action: () => { window.location.href = '/profile/'; }}, {label: 'More options', action: mainSuggestions}]);
        return;
      }
      const {limit, spent, remaining, over} = data.allowance;
      addMessage(`Your daily allowance is ${money(limit)}. You've spent ${money(spent)} today. ${Number(over) > 0 ? `That is ${money(over)} above your allowance.` : `You have ${money(remaining)} left for today.`}${proposed ? ` A ${money(proposed)} purchase would ${proposed <= Number(remaining) ? 'fit within it' : 'be above your remaining allowance'}.` : ''}`);
      mainSuggestions();
    } catch (_) { addMessage('Sorry, I’m having trouble checking your allowance. Please try again in a moment.'); mainSuggestions(); }
  };
  const showBills = async () => {
    try {
      const data = await context();
      addMessage(data.payments.length ? `Here are your payments due in the next 30 days:\n${data.payments.map(item => `${item.name} · ${item.date} · ${money(item.amount)}`).join('\n')}` : 'You have no payments due in the next 30 days.');
    } catch (_) { addMessage('Sorry, I’m having trouble loading your bills. Please try again in a moment.'); }
    mainSuggestions();
  };
  const chooseCategory = async (category) => {
    if (!pendingTransaction) return;
    const txn = pendingTransaction;
    addMessage(`Would you like me to change ${txn.title} to ${category.label}?`);
    showSuggestions([
      {label: 'Confirm change', action: async () => {
        try {
          const response = await fetch('/api/chatbot/tools/', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfToken()}, body: JSON.stringify({transaction_id: txn.id, category: category.key})});
          const data = await response.json();
          if (!response.ok) throw new Error(data.error || 'The update did not go through.');
          addMessage(`Done. ${data.title} is now in ${data.category}.`);
          pendingTransaction = null;
          addedExpense = true;
        } catch (_) { addMessage('Sorry, I couldn’t update that expense. Please try again.'); }
        mainSuggestions();
      }},
      {label: 'Cancel', action: mainSuggestions},
    ]);
  };
  const startCategoryCorrection = async (request = '') => {
    try {
      const data = await context();
      if (!data.recent.length) { addMessage('There are no recent expenses to change yet.'); mainSuggestions(); return; }
      const requested = data.categories.find(category =>
        request.toLowerCase().includes(category.label.toLowerCase()) ||
        request.toLowerCase().includes(category.key.toLowerCase()));
      addMessage('Which recent expense would you like to change?');
      showSuggestions(data.recent.map(txn => ({label: `${txn.title} · ${money(txn.amount)} · ${txn.date}`, action: () => {
        pendingTransaction = txn;
        if (requested) { chooseCategory(requested); return; }
        addMessage(`Please choose a category for ${txn.title}.`);
        showSuggestions(data.categories.map(category => ({label: category.label, action: () => chooseCategory(category)})));
      }})));
    } catch (_) { addMessage('Sorry, I’m having trouble loading your recent expenses. Please try again in a moment.'); mainSuggestions(); }
  };
  const previewExpense = (title) => {
    pendingTitle = title || 'Daily expense';
    step = 'confirm_expense';
    const category = inferCategory(pendingTitle);
    addMessage(`Would you like to add ${money(pendingAmount)} for ${pendingTitle} today under ${category[0].toUpperCase() + category.slice(1)}?`);
    showSuggestions([
      {label: 'Confirm expense', action: () => saveExpense(pendingTitle)},
      {label: 'Cancel', action: () => { addMessage('No problem. I haven’t added that expense.'); resetForAnother(); }},
    ]);
  };

  const warnForAllowance = (amount) => {
    context().then((data) => {
      if (pendingAmount !== amount || !['title', 'confirm_expense'].includes(step) || !data.allowance || warnedAmount === amount) return;
      const remaining = Number(data.allowance.remaining);
      if (amount > remaining) {
        const over = Number(data.allowance.spent) + amount - Number(data.allowance.limit);
        warnedAmount = amount;
        addMessage(`Heads up: this would put today's spending ${money(over)} over your daily allowance. You have ${money(remaining)} left today.`);
      }
    }).catch(() => {});
  };

  const resetForAnother = () => {
    step = 'amount';
    pendingAmount = 0;
    warnedAmount = 0;
    pendingTitle = '';
    input.value = '';
    input.inputMode = 'decimal';
    input.placeholder = 'Enter amount';
    currency.hidden = false;
    orb?.classList.remove('is-hidden');
    showSuggestions();
    addMessage('How much would you like to record?');
    focusInputNow();
  };

  const startConversation = () => {
    const intros = [
      'Hi! I’m here to help you keep track of your spending.',
      'Hello! What would you like to check today?',
      'Welcome back! I can help with expenses, bills, and your allowance.',
      'Hi there! Let’s make your money a little easier to follow.',
      'Hello! Tell me what you would like to record or review.',
    ];
    const storageKey = 'spendwise-chatbot-intro-index';
    const current = Number(window.localStorage.getItem(storageKey) || 0);
    const intro = intros[current % intros.length];
    window.localStorage.setItem(storageKey, String(current + 1));

    addMessage(intro);
    window.setTimeout(() => {
      if (!panel.hidden && step === 'amount' && pendingAmount === 0) {
        addMessage('You can ask about your allowance or bills, update a category, or add an expense.');
        mainSuggestions();
      }
    }, 420);
  };

  const finishChat = () => {
    const goodbyes = [
      'All done for now. I’ll be here whenever you need me.',
      'Thanks for checking in. See you next time!',
      'You’re all set. Come back whenever you would like to review your spending.',
      'That’s everything for now. Take care!',
    ];
    const index = Math.floor(Math.random() * goodbyes.length);
    showSuggestions();
    input.disabled = true;
    addMessage(goodbyes[index]);
    window.clearTimeout(finishTimer);
    finishTimer = window.setTimeout(() => {
      finishTimer = null;
      closeChat();
    }, 3000);
  };

  const saveExpense = async (title, allowanceConfirmed = false) => {
    if (isSaving) return;
    isSaving = true;
    input.disabled = true;
    showSuggestions();
    addMessage('Saving that…');

    try {
      const response = await fetch('/api/transactions/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken(),
        },
        body: JSON.stringify({
          amount: pendingAmount,
          title: title || 'Daily expense',
          category: inferCategory(title || ''),
          txn_type: 'expense',
          date: localDate(),
          warn_on_allowance: true,
          allowance_confirmed: allowanceConfirmed,
        }),
      });
      const data = await response.json();
      messages.lastElementChild?.remove();
      if (response.status === 409 && data.allowance_warning) {
        step = 'confirm_allowance';
        addMessage(data.message);
        showSuggestions([
          { label: 'Add anyway', action: () => saveExpense(title, true) },
          { label: 'Change amount', action: resetForAnother },
        ]);
        return;
      }
      if (!response.ok || !data.success) throw new Error(data.error || 'The expense was not saved.');

      addedExpense = true;
      step = 'complete';
      addMessage(`Done. I’ve added ${CURR_SYMBOL}${pendingAmount.toLocaleString(CURR_LOCALE)} for ${title || 'Daily expense'} today.`);
      addMessage(data.saving_message || 'Thanks for keeping your spending up to date.');
      input.value = '';
      input.placeholder = 'Choose an option below';
      input.inputMode = 'text';
      currency.hidden = true;
      showSuggestions([
        { label: '+ Add another', action: resetForAnother },
        { label: 'More options', action: mainSuggestions },
        { label: 'Done', action: finishChat },
      ]);
    } catch (error) {
      messages.lastElementChild?.remove();
      addMessage(navigator.onLine
        ? 'Sorry, I couldn’t save that expense. Please try again.'
        : 'It looks like you’re offline. Please reconnect and try again.');
      step = 'title';
    } finally {
      isSaving = false;
      input.disabled = false;
    }
  };

  const askAI = async (message) => {
    addMessage(message, 'user');
    input.value = '';
    input.disabled = true;
    showSuggestions();
    step = 'ai';
    const waiting = document.createElement('div');
    waiting.className = 'expense-chatbot-message is-assistant';
    waiting.textContent = 'Thinking…';
    messages.appendChild(waiting);
    try {
      const response = await fetch('/api/chatbot/message/', {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfToken()},
        body: JSON.stringify({message, history: aiHistory.slice(-8)}),
      });
      const data = await response.json();
      waiting.remove();
      if (!response.ok) throw new Error(data.error || 'Sorry, I couldn’t answer just now.');
      addMessage(data.answer);
      aiHistory.push({role: 'user', content: message}, {role: 'assistant', content: data.answer});
      input.placeholder = 'Ask a follow-up or enter an expense';
      input.inputMode = 'text';
      currency.hidden = true;
      showSuggestions([{label: '+ Add expense', action: resetForAnother}, {label: 'More options', action: mainSuggestions}]);
    } catch (error) {
      waiting.remove();
      addMessage(error.message || 'Sorry, I couldn’t answer just now.');
      mainSuggestions();
    } finally {
      input.disabled = false;
    }
  };

  const handleAnswer = (rawValue) => {
    const value = rawValue.trim();
    if (!value || isSaving) return;

    if (/\b(allowance|can i spend|left today|spend today)\b/i.test(value)) {
      addMessage(value, 'user'); input.value = '';
      const proposed = value.match(/(?:₹|\$|rs\.?\s*)?(\d+(?:\.\d{1,2})?)/i);
      checkAllowance(proposed ? Number(proposed[1]) : 0); return;
    }
    if (/\b(due|upcoming bills?|next payment|subscriptions?)\b/i.test(value)) {
      addMessage(value, 'user'); input.value = ''; showBills(); return;
    }
    if (/\b(category|categorize|categorise|reclassify|wrong category)\b/i.test(value) || /^that purchase was\b/i.test(value) || /\bchange\b.+\bto\b/i.test(value)) {
      addMessage(value, 'user'); input.value = ''; startCategoryCorrection(value); return;
    }
    if (step === 'confirm_expense') {
      addMessage(value, 'user'); input.value = '';
      if (/^(yes|confirm|save|add)$/i.test(value)) saveExpense(pendingTitle);
      else if (/^(no|cancel)$/i.test(value)) { addMessage('No problem. I haven’t added that expense.'); resetForAnother(); }
      else addMessage('Please choose Confirm expense or Cancel below.');
      return;
    }

    if (step === 'confirm_allowance') {
      addMessage(value, 'user'); input.value = '';
      if (/^(yes|confirm|add|add anyway)$/i.test(value)) saveExpense(pendingTitle, true);
      else if (/^(no|cancel|change|change amount)$/i.test(value)) resetForAnother();
      else addMessage('Please choose Add anyway or Change amount below.');
      return;
    }

    if (step === 'amount' || step === 'ai') {
      if (/^(how|what|why|when|where|explain|tell me|help me)\b/i.test(value)
          && !/\b(add|record|spent|paid)\b/i.test(value)) {
        askAI(value);
        return;
      }
      const symPattern = CURR_SYMBOL === '$' ? '\\$' : '₹';
      const normalizedValue = value.replace(/,/g, '');
      const match = normalizedValue.match(new RegExp(`(?:${symPattern}|rs\.?\\s*)?(\\d+(?:\\.\\d{1,2})?)`, 'i'));
      const amount = match ? Number(match[1]) : 0;
      if (!amount || amount <= 0) {
        askAI(value);
        return;
      }

      pendingAmount = amount;
      warnedAmount = 0;
      orb?.classList.add('is-hidden');
      addMessage(`${CURR_SYMBOL}${amount.toLocaleString(CURR_LOCALE)}`, 'user');
      const possibleTitle = normalizedValue.replace(match[0], '').replace(/^(?:i\s+)?(?:spent|paid)\b/i, '').replace(/^\s*(?:on|for)\b/i, '').trim();
      input.value = '';
      if (possibleTitle) {
        previewExpense(possibleTitle);
        warnForAllowance(amount);
        return;
      }

      previewExpense('Expense');
      warnForAllowance(amount);
      return;
    }

    if (step === 'title') {
      addMessage(value, 'user');
      input.value = '';
      previewExpense(value);
    }
  };

  function openChat() {
    window.clearTimeout(closeTimer);
    window.clearTimeout(finishTimer);
    dismissHint();
    try {
      window.localStorage.setItem('spendwise-chatbot-hint-seen', 'true');
    } catch (error) {
      // Ignore private-mode storage failures; the hint is purely cosmetic.
    }
    closeTimer = null;
    finishTimer = null;
    panel.hidden = false;
    backdrop.hidden = false;
    document.body.classList.add('expense-chatbot-open');
    fab.setAttribute('aria-expanded', 'true');
    panel.classList.add('is-open');
    backdrop.classList.add('is-open');
    if (!messages.children.length) {
      startConversation();
    }
    focusInputNow();
  }

  function closeChat() {
    window.clearTimeout(closeTimer);
    window.clearTimeout(finishTimer);
    finishTimer = null;
    panel.classList.remove('is-open');
    backdrop.classList.remove('is-open');
    document.body.classList.remove('expense-chatbot-open');
    document.body.classList.remove('expense-chatbot-keyboard-open');
    document.body.classList.remove('expense-chatbot-input-active');
    fab.setAttribute('aria-expanded', 'false');
    closeTimer = window.setTimeout(() => {
      panel.hidden = true;
      backdrop.hidden = true;
      closeTimer = null;
      if (addedExpense && root.dataset.dashboard === 'true') {
        window.sessionStorage.setItem('spendwise-skip-chatbot-once', 'true');
        window.location.reload();
        return;
      }
      step = 'amount';
      pendingAmount = 0;
      addedExpense = false;
      input.disabled = false;
      input.value = '';
      input.placeholder = 'Enter amount';
      input.inputMode = 'decimal';
      currency.hidden = false;
      orb?.classList.remove('is-hidden');
      messages.replaceChildren();
      suggestions.replaceChildren();
    }, 220);
  }

  fab.addEventListener('click', openChat);
  hint?.addEventListener('click', openChat);
  closeButton.addEventListener('click', closeChat);
  backdrop.addEventListener('click', closeChat);
  const submitAnswer = () => {
    handleAnswer(input.value);
  };

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    submitAnswer();
  });
  sendButton?.addEventListener('pointerdown', (event) => {
    if (event.pointerType !== 'touch') return;
    event.preventDefault();
    submitAnswer();
    if (!input.disabled) {
      input.focus({ preventScroll: true });
      syncVisualViewport();
    }
  });
  input.addEventListener('focus', () => {
    window.clearTimeout(inputBlurTimer);
    document.body.classList.add('expense-chatbot-input-active');
    syncVisualViewport();
  });
  input.addEventListener('blur', () => {
    window.clearTimeout(inputBlurTimer);
    inputBlurTimer = window.setTimeout(() => {
      if (document.activeElement !== input && document.activeElement !== sendButton) {
        document.body.classList.remove('expense-chatbot-input-active');
      }
    }, 140);
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !panel.hidden) closeChat();
  });

  document.addEventListener('touchstart', (event) => {
    if (window.innerWidth > 600 || !panel.hidden || event.touches.length !== 1) {
      swipeStart = null;
      return;
    }
    const touch = event.touches[0];
    const startsNearBottom = touch.clientY >= window.innerHeight - 150;
    swipeStart = startsNearBottom ? { x: touch.clientX, y: touch.clientY } : null;
  }, { passive: true });

  window.visualViewport?.addEventListener('resize', syncVisualViewport);
  window.visualViewport?.addEventListener('scroll', syncVisualViewport);

  document.addEventListener('touchend', (event) => {
    if (!swipeStart || window.innerWidth > 600 || !panel.hidden) {
      swipeStart = null;
      return;
    }
    const touch = event.changedTouches[0];
    const verticalDistance = swipeStart.y - touch.clientY;
    const horizontalDistance = Math.abs(swipeStart.x - touch.clientX);
    swipeStart = null;

    if (verticalDistance >= 65 && horizontalDistance <= 70) {
      openChat();
    }
  }, { passive: true });

  try {
    const hintSeen = window.localStorage.getItem('spendwise-chatbot-hint-seen') === 'true';
    if (hint && !hintSeen) {
      hintTimer = window.setTimeout(() => {
        if (!panel.hidden) return;
        hint.hidden = false;
        window.requestAnimationFrame(() => hint.classList.add('is-visible'));
      }, 900);
    }
  } catch (error) {
    // If localStorage is unavailable, keep the assistant manual and skip the hint.
  }

})();
