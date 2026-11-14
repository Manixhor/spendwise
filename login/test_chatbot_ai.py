import json
from unittest.mock import patch, MagicMock

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse


class ChatbotAITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='ai-user')
        self.client.force_login(self.user)

    @override_settings(OPENAI_API_KEY='', GROQ_API_KEY='')
    def test_missing_key_is_clear(self):
        response = self.client.post(reverse('chatbot_message'),
                                    data=json.dumps({'message': 'How do I budget?'}),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 503)
        self.assertIn('not configured', response.json()['error'])

    @override_settings(OPENAI_API_KEY='test-key', GROQ_API_KEY='')
    @patch('login.chatbot_ai.urllib.request.urlopen')
    def test_general_reply_does_not_include_account_records(self, urlopen):
        context = MagicMock()
        context.read.return_value = json.dumps({'output': [{'content': [{'text': 'Try a small weekly budget.'}]}]}).encode()
        urlopen.return_value.__enter__.return_value = context
        response = self.client.post(reverse('chatbot_message'),
                                    data=json.dumps({'message': 'How do I budget?'}),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertIn('weekly budget', response.json()['answer'])
        request = urlopen.call_args.args[0]
        payload = json.loads(request.data)
        self.assertFalse(payload['store'])
        self.assertEqual(payload['input'], [{'role': 'user', 'content': 'How do I budget?'}])

    @override_settings(OPENAI_API_KEY='', GROQ_API_KEY='test-groq-key')
    @patch('login.chatbot_ai.urllib.request.urlopen')
    def test_groq_greeting_uses_conversation(self, urlopen):
        context = MagicMock()
        context.read.return_value = json.dumps({'choices': [{'message': {'content': 'Hi! How has your day been?'}}]}).encode()
        urlopen.return_value.__enter__.return_value = context
        response = self.client.post(reverse('chatbot_message'), data=json.dumps({
            'message': 'hi',
            'history': [{'role': 'user', 'content': 'I am planning my week.'}],
        }), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Hi!', response.json()['answer'])
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, 'https://api.groq.com/openai/v1/chat/completions')
        payload = json.loads(request.data)
        self.assertEqual(payload['messages'][-2:], [
            {'role': 'user', 'content': 'I am planning my week.'},
            {'role': 'user', 'content': 'hi'},
        ])
