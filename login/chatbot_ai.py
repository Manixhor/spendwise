"""Optional general conversation for the SpendWise assistant."""

import json
import logging
import urllib.error
import urllib.request
from urllib.parse import quote

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)


def _response_text(payload):
    return ' '.join(
        part['text'].strip()
        for item in payload.get('output', []) if isinstance(item, dict)
        for part in item.get('content', []) if isinstance(part, dict)
        if isinstance(part.get('text'), str) and part['text'].strip()
    ).strip()


def _gemini_text(payload):
    return ' '.join(
        part['text'].strip()
        for candidate in payload.get('candidates', []) if isinstance(candidate, dict)
        for part in candidate.get('content', {}).get('parts', []) if isinstance(part, dict)
        if isinstance(part.get('text'), str) and part['text'].strip()
    ).strip()


@login_required(login_url='/login/')
@require_POST
def chatbot_message(request):
    gemini_key = getattr(settings, 'GEMINI_API_KEY', '')
    groq_key = getattr(settings, 'GROQ_API_KEY', '')
    openai_key = settings.OPENAI_API_KEY
    try:
        data = json.loads(request.body)
        message = data['message'].strip()
        history = data.get('history', [])
        if not message or len(message) > 2000 or not isinstance(history, list):
            raise ValueError
        clean_history = [
            {'role': item['role'], 'content': item['content']}
            for item in history[-8:]
            if isinstance(item, dict)
            and item.get('role') in ('user', 'assistant')
            and isinstance(item.get('content'), str)
            and len(item['content']) <= 2000
        ]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({'error': 'Please send a shorter message.'}, status=400)
    if not (gemini_key or groq_key or openai_key):
        if message.lower().rstrip('!. ') in ('hi', 'hello', 'hey', 'good morning', 'good evening'):
            return JsonResponse({'answer': 'Hi! What would you like to do today? I can help with an expense, your allowance, or upcoming bills.'})
        return JsonResponse({'error': 'AI chat is not configured yet. You can still add expenses and check your allowance or bills.'}, status=503)
    rate_key = f'chatbot-ai-hour-{request.user.pk}'
    if not cache.add(rate_key, 1, 3600):
        try:
            count = cache.incr(rate_key)
        except ValueError:
            count = 1
        if count > 30:
            return JsonResponse({'error': 'You have reached the chat limit for now. Please try again later.'}, status=429)
    instructions = (
        'You are the SpendWise assistant. Speak naturally, warmly, and briefly. '
        'If greeted, greet back and ask how you can help; do not give a generic help menu unless useful. '
        'Remember the recent conversation and answer follow-up questions directly. '
        'Help with general budgeting and app questions. You do not have access to '
        'the user’s account data here. Do not claim to have added or changed a transaction. '
        'For account-specific actions, suggest using the assistant’s expense, allowance, '
        'bills, or category options. Do not give definitive investment, tax, or legal advice.'
    )
    if gemini_key:
        contents = [
            {'role': 'model' if item['role'] == 'assistant' else 'user',
             'parts': [{'text': item['content']}]}
            for item in clean_history
        ] + [{'role': 'user', 'parts': [{'text': message}]}]
        payload = {
            'systemInstruction': {'parts': [{'text': instructions}]},
            'contents': contents,
            'generationConfig': {'maxOutputTokens': 350},
        }
        model = quote(getattr(settings, 'GEMINI_CHAT_MODEL', 'gemini-flash-lite-latest'), safe='-._')
        endpoint = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
        headers = {'x-goog-api-key': gemini_key}
        provider = 'Gemini'
    elif groq_key:
        payload = {
            'model': getattr(settings, 'GROQ_CHAT_MODEL', 'openai/gpt-oss-120b'),
            'messages': [{'role': 'system', 'content': instructions}]
                        + clean_history + [{'role': 'user', 'content': message}],
            'max_completion_tokens': 350,
        }
        endpoint = 'https://api.groq.com/openai/v1/chat/completions'
        headers = {'Authorization': f'Bearer {groq_key}'}
        provider = 'Groq'
    else:
        payload = {
            'model': getattr(settings, 'OPENAI_CHAT_MODEL', 'gpt-4.1-mini'),
            'instructions': instructions,
            'input': clean_history + [{'role': 'user', 'content': message}],
            'max_output_tokens': 350,
            'store': False,
        }
        endpoint = 'https://api.openai.com/v1/responses'
        headers = {'Authorization': f'Bearer {openai_key}'}
        provider = 'OpenAI'
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode(),
        headers={**headers, 'Content-Type': 'application/json', 'User-Agent': 'SpendWise/1.0'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            result = json.loads(response.read())
            if gemini_key:
                answer = _gemini_text(result)
            elif groq_key:
                choices = result.get('choices') or [{}]
                answer = choices[0].get('message', {}).get('content', '')
            else:
                answer = _response_text(result)
    except urllib.error.HTTPError as exc:
        logger.warning('AI chat provider returned HTTP %s (%s)', exc.code, provider)
        return JsonResponse({'error': 'Sorry, I couldn’t answer just now. Please try again.'}, status=502)
    except (urllib.error.URLError, ValueError, TimeoutError) as exc:
        logger.warning('AI chat provider request failed (%s)', type(exc).__name__)
        return JsonResponse({'error': 'Sorry, I couldn’t answer just now. Please try again.'}, status=502)
    if not answer:
        return JsonResponse({'error': 'Sorry, I couldn’t answer just now. Please try again.'}, status=502)
    return JsonResponse({'answer': answer[:3000]})
