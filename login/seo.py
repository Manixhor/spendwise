from xml.sax.saxutils import escape

from django.http import HttpResponse
from django.urls import reverse
from django.views.decorators.http import require_GET


PUBLIC_SEARCH_PAGES = ("onboarding", "android_download", "privacy_policy")


@require_GET
def sitemap(request):
    urls = [request.build_absolute_uri(reverse(name)) for name in PUBLIC_SEARCH_PAGES]
    items = "".join(f"<url><loc>{escape(url)}</loc></url>" for url in urls)
    body = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{items}</urlset>'
    return HttpResponse(body, content_type="application/xml; charset=utf-8")


@require_GET
def robots_txt(request):
    sitemap_url = request.build_absolute_uri(reverse("sitemap"))
    body = f"User-agent: *\nAllow: /\n\nSitemap: {sitemap_url}\n"
    return HttpResponse(body, content_type="text/plain; charset=utf-8")
