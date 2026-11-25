import os
import tempfile
import zipfile
from io import BytesIO
import unittest
from pathlib import Path
from unittest.mock import patch
from werkzeug.security import generate_password_hash

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
        self.cover_dir = Path(self.temp_dir.name) / "covers"
        self.cover_dir.mkdir()
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
        self.cover_patch = patch("app.COVER_IMAGE_DIR", self.cover_dir)
        self.articles_patch.start()
        self.pdf_patch.start()
        self.cover_patch.start()
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=True, SECRET_KEY="test-secret-key")
        self.client = app.test_client()

    def tearDown(self):
        self.articles_patch.stop()
        self.pdf_patch.stop()
        self.cover_patch.stop()
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
        self.assertIn(b"User-agent: *\n", response.data)
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




    def test_admin_session_cookie_uses_safe_defaults(self):
        self.assertTrue(app.config["SESSION_COOKIE_HTTPONLY"])
        self.assertEqual(app.config["SESSION_COOKIE_SAMESITE"], "Lax")
        self.assertEqual(app.config["PERMANENT_SESSION_LIFETIME"].total_seconds(), 1800)

    def test_successful_login_creates_a_permanent_session(self):
        with patch.dict(app.config, {
            "WTF_CSRF_ENABLED": False,
            "ADMIN_USERNAME": "test-admin",
            "ADMIN_PASSWORD_HASH": generate_password_hash("correct-password")
        }):
            response = self.client.post("/admin/login", data={
                "username": "test-admin",
                "password": "correct-password"
            })
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as session:
            self.assertTrue(session.get("admin_logged_in"))
            self.assertTrue(session.permanent)

    def test_admin_post_without_csrf_token_is_rejected(self):
        response = self.client.post("/admin/login", data={
            "username": "test-admin",
            "password": "incorrect"
        })
        self.assertEqual(response.status_code, 400)

    def test_login_form_contains_csrf_token(self):
        response = self.client.get("/admin/login")
        self.assertEqual(response.status_code, 200)
        self.assertIn('name="csrf_token"', response.get_data(as_text=True))

    def test_logout_requires_post(self):
        with self.client.session_transaction() as session:
            session["admin_logged_in"] = True
        response = self.client.get("/admin/logout")
        self.assertEqual(response.status_code, 405)

    def test_dashboard_requires_admin_login(self):
        response = self.client.get("/admin/dashboard")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login", response.headers["Location"])


    def test_backup_requires_admin_login(self):
        response = self.client.get("/admin/backup")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login", response.headers["Location"])

    def test_admin_can_download_backup_with_articles_and_book_pdfs(self):
        (self.pdf_dir / "sample-book.pdf").write_bytes(b"%PDF-test-content")
        with self.client.session_transaction() as session:
            session["admin_logged_in"] = True

        response = self.client.get("/admin/backup")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/zip")
        self.assertIn("attachment;", response.headers["Content-Disposition"])

        with zipfile.ZipFile(BytesIO(response.data)) as backup_zip:
            names = backup_zip.namelist()
            self.assertIn("articles/published-test-article.md", names)
            self.assertIn("articles/private-draft-article.md", names)
            self.assertIn("book_pdfs/sample-book.pdf", names)
            self.assertIn("BACKUP-INFO.txt", names)
            self.assertEqual(backup_zip.read("book_pdfs/sample-book.pdf"), b"%PDF-test-content")

    def test_admin_dashboard_shows_article_counts(self):
        with self.client.session_transaction() as session:
            session["admin_logged_in"] = True
        response = self.client.get("/admin/dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Total articles", response.data)
        self.assertIn(b"Published Test Article", response.data)
        self.assertIn(b"Private Draft Article", response.data)

    def test_dashboard_can_filter_drafts(self):
        with self.client.session_transaction() as session:
            session["admin_logged_in"] = True
        response = self.client.get("/admin/dashboard?status=draft")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Private Draft Article", response.data)
        self.assertNotIn(b"Published Test Article", response.data)

    def test_dashboard_can_search_article_titles(self):
        with self.client.session_transaction() as session:
            session["admin_logged_in"] = True
        response = self.client.get("/admin/dashboard?q=Published")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Published Test Article", response.data)
        self.assertNotIn(b"Private Draft Article", response.data)


    def test_admin_can_create_article_with_valid_cover_image(self):
        with self.client.session_transaction() as session:
            session["admin_logged_in"] = True

        image_bytes = b"\\x89PNG\\r\\n\\x1a\\n" + b"\\x00" * 8
        with patch.dict(app.config, {"WTF_CSRF_ENABLED": False}):
            response = self.client.post("/admin/articles/add", data={
                "title": "Cover Upload Test",
                "date": "2026-11-25",
                "category": "Testing",
                "content": "An article with a cover.",
                "published": "on",
                "cover_image": (BytesIO(image_bytes), "cover.png")
            }, content_type="multipart/form-data")

        self.assertEqual(response.status_code, 302)
        post = frontmatter.load(str(self.articles_dir / "cover-upload-test.md"))
        cover_path = post.metadata["cover_image"]
        self.assertTrue(cover_path.startswith("uploads/covers/"))
        saved_file = self.cover_dir / Path(cover_path).name
        self.assertTrue(saved_file.is_file())

        homepage = self.client.get("/")
        self.assertIn(cover_path.encode(), homepage.data)
        article_page = self.client.get("/article/cover-upload-test")
        self.assertIn(cover_path.encode(), article_page.data)

    def test_cover_upload_rejects_unsupported_file_types(self):
        with self.client.session_transaction() as session:
            session["admin_logged_in"] = True

        with patch.dict(app.config, {"WTF_CSRF_ENABLED": False}):
            response = self.client.post("/admin/articles/add", data={
                "title": "Invalid Cover Test",
                "date": "2026-11-25",
                "content": "This should not be saved.",
                "cover_image": (BytesIO(b"not an image"), "cover.gif")
            }, content_type="multipart/form-data")

        self.assertEqual(response.status_code, 200)
        self.assertFalse((self.articles_dir / "invalid-cover-test.md").exists())
        self.assertEqual(list(self.cover_dir.iterdir()), [])

    def test_editing_article_without_new_cover_keeps_existing_image(self):
        cover_file = self.cover_dir / "existing-cover.png"
        cover_file.write_bytes(b"\\x89PNG\\r\\n\\x1a\\n" + b"\\x00" * 8)
        post = frontmatter.Post(
            "Original article content.",
            title="Published Test Article",
            date="2026-11-15",
            category="Testing",
            published=True,
            cover_image="uploads/covers/existing-cover.png"
        )
        frontmatter.dump(post, str(self.articles_dir / "published-test-article.md"))

        with self.client.session_transaction() as session:
            session["admin_logged_in"] = True

        with patch.dict(app.config, {"WTF_CSRF_ENABLED": False}):
            response = self.client.post(
                "/admin/articles/published-test-article/edit",
                data={
                    "title": "Published Test Article",
                    "date": "2026-11-15",
                    "category": "Testing",
                    "content": "Updated article content.",
                    "published": "on"
                }
            )

        self.assertEqual(response.status_code, 302)
        updated = frontmatter.load(str(self.articles_dir / "published-test-article.md"))
        self.assertEqual(updated.metadata["cover_image"], "uploads/covers/existing-cover.png")
        self.assertTrue(cover_file.is_file())




if __name__ == "__main__":
    unittest.main()
