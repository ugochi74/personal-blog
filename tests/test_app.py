import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("ADMIN_USERNAME", "test-admin")
os.environ.setdefault("ADMIN_PASSWORD_HASH", "scrypt:32768:8:1$test$test")

import frontmatter
from app import app


class BlogRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.articles_dir = Path(self.temp_dir.name) / "articles"
        self.pdf_dir = Path(self.temp_dir.name) / "book_pdfs"
        self.articles_dir.mkdir()
        self.pdf_dir.mkdir()
        published = frontmatter.Post(
            "A short article for testing the public blog.", title="Published Test Article",
            date="2026-11-15", category="Testing", excerpt="A test article summary.", published=True,
        )
        draft = frontmatter.Post(
            "This draft must remain private.", title="Private Draft Article",
            date="2026-11-15", category="Testing", published=False,
        )
        frontmatter.dump(published, str(self.articles_dir / "published-test-article.md"))
        frontmatter.dump(draft, str(self.articles_dir / "private-draft-article.md"))
        self.articles_patch = patch("app.ARTICLES_DIR", self.articles_dir)
        self.pdf_patch = patch("app.BOOK_PDF_DIR", self.pdf_dir)
        self.articles_patch.start()
        self.pdf_patch.start()
        app.config.update(TESTING=True, SECRET_KEY="test-secret-key")
        self.client = app.test_client()

    def tearDown(self):
        self.articles_patch.stop()
        self.pdf_patch.stop()
        self.temp_dir.cleanup()

    def test_homepage_only_lists_published_articles(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Published Test Article", response.data)
        self.assertNotIn(b"Private Draft Article", response.data)

    def test_draft_article_is_not_public(self):
        response = self.client.get("/article/private-draft-article")
        self.assertEqual(response.status_code, 404)

    def test_rss_feed_contains_published_articles_only(self):
        response = self.client.get("/feed.xml")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Published Test Article", response.data)
        self.assertNotIn(b"Private Draft Article", response.data)

    def test_sitemap_contains_public_pages_only(self):
        response = self.client.get("/sitemap.xml")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"/article/published-test-article", response.data)
        self.assertNotIn(b"private-draft-article", response.data)

    def test_robots_file_disallows_admin_area(self):
        response = self.client.get("/robots.txt")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Disallow: /admin/", response.data)
        self.assertIn(b"User-agent: *\\n", response.data)
        self.assertIn(b"Sitemap:", response.data)

    def test_security_headers_are_present(self):
        response = self.client.get("/")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["X-Frame-Options"], "SAMEORIGIN")
        self.assertEqual(response.headers["Referrer-Policy"], "strict-origin-when-cross-origin")

    def test_custom_not_found_page_is_rendered(self):
        response = self.client.get("/this-page-does-not-exist")
        self.assertEqual(response.status_code, 404)
        self.assertIn(b"We couldn't find that page", response.data)


if __name__ == "__main__":
    unittest.main()
