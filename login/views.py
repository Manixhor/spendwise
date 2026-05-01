from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


def onboarding(request: HttpRequest) -> HttpResponse:
    return render(request, "login/onboarding.html")


def signup(request: HttpRequest) -> HttpResponse:
    return render(request, "login/signup.html")


def login_view(request: HttpRequest) -> HttpResponse:
    return render(request, "login/login.html")


def dashboard(request: HttpRequest) -> HttpResponse:
    return render(request, "login/dashboard.html")
