(() => {
  const root = document.getElementById('expenseChatbot');
  if (!root || root.dataset.ready === 'true') return;
  root.dataset.ready = 'true';

  const fab = document.getElementById('expenseChatbotFab');
  const panel = document.getElementById('expenseChatbotPanel');
  const backdrop = document.getElementById('expenseChatbotBackdrop');
  const closeButton = document.getElementById('expenseChatbotClose');
  const messages = document.getElementById('expenseChatbotMessages');
  const suggestions = document.getElementById('expenseChatbotSuggestions');
  const form = document.getElementById('expenseChatbotForm');
  const input = document.getElementById('expenseChatbotInput');
  const currency = document.getElementById('expenseChatbotCurrency');
  const orb = document.getElementById('expenseChatbotOrb');

  let step = 'amount';
  let pendingAmount = 0;
  let addedExpense = false;
  let isSaving = false;
  let closeTimer = null;
  let finishTimer = null;
  let swipeStart = null;

  const syncVisualViewport = () => {
    if (!window.visualViewport) return;
    const viewport = window.visualViewport;
    const layoutHeight = document.documentElement.clientHeight;
    const keyboardOffset = Math.max(
      0,
      layoutHeight - viewport.height - viewport.offsetTop,
    );
    root.style.setProperty('--chat-visual-height', `${viewport.height}px`);
    root.style.setProperty('--chat-keyboard-offset', `${keyboardOffset}px`);
    document.body.classList.toggle(
      'expense-chatbot-keyboard-open',
      !panel.hidden && keyboardOffset > 120,
    );
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

  const resetForAnother = () => {
    step = 'amount';
    pendingAmount = 0;
    input.value = '';
    input.inputMode = 'decimal';
    input.placeholder = 'Enter amount';
    currency.hidden = false;
    orb?.classList.remove('is-hidden');
    showSuggestions();
    addMessage('How much did you spend today?');
    input.focus();
  };

  const startConversation = () => {
    const intros = [
      'Hi! Your wallet and I had a quick meeting. We agreed to track today.',
      'Hello! Money talks, but today we are making it explain where it went.',
      'Hi there! No judgement here. Even coffee deserves accurate accounting.',
      'Welcome back! Let’s solve today’s tiny financial mystery.',
      'Hey! Your budget is awake, caffeinated, and ready for the truth.',
    ];
    const storageKey = 'spendwise-chatbot-intro-index';
    const current = Number(window.localStorage.getItem(storageKey) || 0);
    const intro = intros[current % intros.length];
    window.localStorage.setItem(storageKey, String(current + 1));

    addMessage(intro);
    window.setTimeout(() => {
      if (!panel.hidden) addMessage('How much did you spend today?');
    }, 420);
    input.focus();
  };

  const finishChat = () => {
    const goodbyes = [
      'Goodbye for now. Save a little today so future you can spend with a smile.',
      'All caught up. Keep your savings growing, one smart choice at a time.',
      'See you soon. Your future wallet says thank you for tracking today.',
      'That is everything. Small savings today make bigger plans possible tomorrow.',
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

  const saveExpense = async (title) => {
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
        }),
      });
      const data = await response.json();
      messages.lastElementChild?.remove();
      if (!response.ok || !data.success) throw new Error(data.error || 'Could not save expense.');

      addedExpense = true;
      step = 'complete';
      addMessage(`Thank you. ₹${pendingAmount.toLocaleString('en-IN')} for ${title || 'Daily expense'} is added for today.`);
      addMessage(data.saving_message || 'Tracked money behaves better than mystery money. Nice catch.');
      input.value = '';
      input.placeholder = 'Choose an option below';
      input.inputMode = 'text';
      currency.hidden = true;
      showSuggestions([
        { label: '+ Add another', action: resetForAnother },
        { label: 'Done', action: finishChat },
      ]);
    } catch (error) {
      messages.lastElementChild?.remove();
      addMessage(navigator.onLine
        ? 'I could not save that one. Please try again.'
        : 'Your internet is taking a break. Reconnect and I’ll be ready.');
      step = 'title';
    } finally {
      isSaving = false;
      input.disabled = false;
    }
  };

  const handleAnswer = (rawValue) => {
    const value = rawValue.trim();
    if (!value || isSaving) return;

    if (step === 'amount') {
      const match = value.replace(/,/g, '').match(/(?:₹|rs\.?\s*)?(\d+(?:\.\d{1,2})?)/i);
      const amount = match ? Number(match[1]) : 0;
      if (!amount || amount <= 0) {
        addMessage(value, 'user');
        addMessage('Give me an amount greater than zero, for example ₹250.');
        return;
      }

      pendingAmount = amount;
      orb?.classList.add('is-hidden');
      addMessage(`₹${amount.toLocaleString('en-IN')}`, 'user');
      const possibleTitle = value.replace(match[0], '').trim();
      input.value = '';
      if (possibleTitle) {
        saveExpense(possibleTitle);
        return;
      }

      step = 'title';
      currency.hidden = true;
      input.inputMode = 'text';
      input.placeholder = 'e.g. Lunch, cab, coffee';
      addMessage('What was it for?');
      showSuggestions([{ label: 'Skip', action: () => saveExpense('Daily expense') }]);
      return;
    }

    if (step === 'title') {
      addMessage(value, 'user');
      input.value = '';
      saveExpense(value);
    }
  };

  function openChat() {
    window.clearTimeout(closeTimer);
    window.clearTimeout(finishTimer);
    closeTimer = null;
    finishTimer = null;
    panel.hidden = false;
    backdrop.hidden = false;
    document.body.classList.add('expense-chatbot-open');
    fab.setAttribute('aria-expanded', 'true');
    panel.classList.add('is-open');
    backdrop.classList.add('is-open');
    if (!messages.children.length) startConversation();
    input.focus({ preventScroll: true });
    window.setTimeout(syncVisualViewport, 80);
  }

  function closeChat() {
    window.clearTimeout(closeTimer);
    panel.classList.remove('is-open');
    backdrop.classList.remove('is-open');
    document.body.classList.remove('expense-chatbot-open');
    document.body.classList.remove('expense-chatbot-keyboard-open');
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
  closeButton.addEventListener('click', closeChat);
  backdrop.addEventListener('click', closeChat);
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    handleAnswer(input.value);
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

  if (root.dataset.dashboard === 'true') {
    const skipOnce = window.sessionStorage.getItem('spendwise-skip-chatbot-once') === 'true';
    window.sessionStorage.removeItem('spendwise-skip-chatbot-once');
    if (!skipOnce) openChat();
  }
})();
