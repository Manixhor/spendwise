"""Render /office/ and syntax-check the inline JS with node."""
import pathlib
import re

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import OfficeEntry
from decimal import Decimal


class OfficeInlineScriptSyntaxTests(TestCase):
    def test_inline_script_parses_with_node(self):
        user = User.objects.create_user(
            username="js@example.com", email="js@example.com", password="secret123"
        )
        OfficeEntry.objects.create(
            user=user, direction="came", amount=Decimal("10"), name="Ravi"
        )
        self.client.force_login(user)

        for i in range(12):
            OfficeEntry.objects.create(
                user=user, direction="taken", amount=Decimal("5"), name=f"P{i}"
            )

        html = self.client.get(reverse("office")).content.decode()
        blocks = re.findall(r"<script>(.*?)</script>", html, re.S)
        self.assertTrue(blocks, "no inline script found")
        source = blocks[-1]

        # Nothing unrendered should survive into the page.
        self.assertNotIn("{{", source)
        self.assertNotIn("{%", source)

        out = pathlib.Path("/tmp/office_rendered.js")
        out.write_text(source)

        import shutil
        import subprocess

        node = shutil.which("node")
        if not node:
            self.skipTest("node is not installed")

        result = subprocess.run(
            [node, "--check", str(out)], capture_output=True, text=True
        )
        self.assertEqual(
            result.returncode,
            0,
            f"node --check failed:\n{result.stdout}\n{result.stderr}",
        )
