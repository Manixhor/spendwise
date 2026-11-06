import re


def is_android_webview(request):
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    return bool(re.search(r'SpendwiseAndroid/|; wv\)', user_agent, re.I))


def android_app(request):
    return {'is_android_app': is_android_webview(request)}
