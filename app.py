
from pathlib import Path
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile
from datetime import datetime
from email.utils import format_datetime
from xml.etree import ElementTree as ET
from functools import wraps
from urllib.parse import urlparse
from uuid import uuid4

import frontmatter
import markdown

from flask_wtf.csrf import CSRFProtect

from flask import (
    Flask,
    render_template,
    abort,
    request,
    redirect,
    url_for,
    session,
    flash,
    send_file,
    Response
)

from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename

from pdf_generator import create_article_pdf


app = Flask(__name__)

# Load application configuration
app.config.from_object("config.Config")

# Protect every POST request against cross-site request forgery.
csrf = CSRFProtect(app)


# Locate the articles directory
ARTICLES_DIR = Path(__file__).parent / "articles"
BOOK_PDF_DIR = Path(__file__).parent / "static" / "book_pdfs"
BOOK_PDF_DIR.mkdir(parents=True, exist_ok=True)
COVER_IMAGE_DIR = Path(__file__).parent / "static" / "uploads" / "covers"
COVER_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
MAX_COVER_IMAGE_SIZE = 5 * 1024 * 1024
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024


# Check required environment configuration
if not app.config["SECRET_KEY"]:
    raise RuntimeError("SECRET_KEY is missing from .env")

if not app.config["ADMIN_USERNAME"]:
    raise RuntimeError("ADMIN_USERNAME is missing from .env")

if not app.config["ADMIN_PASSWORD_HASH"]:
    raise RuntimeError("ADMIN_PASSWORD_HASH is missing from .env")


# Get every article for the admin dashboard, including drafts
def get_all_articles():
    articles = []

    for article_file in ARTICLES_DIR.glob("*.md"):
        post = frontmatter.load(article_file)

        article = {
            "slug": article_file.stem,
            "title": post.metadata.get("title", "Untitled"),
            "date": str(post.metadata.get("date", "")),
            "category": post.metadata.get("category", "General"),
            "content": post.content,
            "published": post.metadata.get("published", True),
            "excerpt": post.metadata.get("excerpt", ""),
            "featured": post.metadata.get("featured", False),
            "cover_image": post.metadata.get("cover_image", ""),
        }

        articles.append(article)

    articles.sort(
        key=lambda article: article["date"],
        reverse=True
    )

    return articles


# Public pages should only show published articles
def get_articles():
    return [
        article for article in get_all_articles()
        if article["published"]
    ]


def estimate_reading_time(content):
    """Estimate reading time using 200 words per minute."""
    word_count = len(content.split())
    return max(1, (word_count + 199) // 200)


def is_valid_book_url(value):
    if not value:
        return True
    parsed_url = urlparse(value)
    return parsed_url.scheme in {"http", "https"} and bool(parsed_url.netloc)


def valid_book_pdf(upload):
    if not upload or not upload.filename or not upload.filename.lower().endswith(".pdf"):
        return False
    file_header = upload.stream.read(5)
    upload.stream.seek(0)
    return file_header == b"%PDF-"


def valid_cover_image(upload):
    """Accept small JPEG, PNG, and WebP images based on their file signatures."""
    if not upload or not upload.filename:
        return False

    extension = Path(upload.filename).suffix.lower()
    if extension not in {".jpg", ".jpeg", ".png", ".webp"}:
        return False

    upload.stream.seek(0, 2)
    file_size = upload.stream.tell()
    upload.stream.seek(0)
    if file_size == 0 or file_size > MAX_COVER_IMAGE_SIZE:
        return False

    header = upload.stream.read(12)
    upload.stream.seek(0)

    if extension in {".jpg", ".jpeg"}:
        return header.startswith(b"\xff\xd8\xff")
    if extension == ".png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    return header.startswith(b"RIFF") and header[8:12] == b"WEBP"


def save_cover_image(upload, slug):
    """Save a validated image under a unique filename and return its static path."""
    extension = Path(upload.filename).suffix.lower()
    filename = f"{slug}-{uuid4().hex}{extension}"
    upload.save(COVER_IMAGE_DIR / filename)
    return f"uploads/covers/{filename}"


def remove_cover_image(cover_image):
    """Delete a cover only when its resolved path stays inside the cover directory."""
    if not cover_image:
        return

    cover_path = (Path(__file__).parent / "static" / cover_image).resolve()
    cover_directory = COVER_IMAGE_DIR.resolve()
    if cover_path.parent == cover_directory and cover_path.is_file():
        cover_path.unlink()


# Protect admin routes
def login_required(function):
    @wraps(function)
    def decorated_function(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("login"))

        return function(*args, **kwargs)

    return decorated_function


# Homepage
@app.route("/")
def home():
    all_articles = get_articles()
    search_query = request.args.get("q", "").strip()
    selected_category = request.args.get("category", "").strip()

    categories = sorted({
        article["category"] for article in all_articles
    })

    articles = all_articles

    if selected_category:
        articles = [
            article for article in articles
            if article["category"].casefold() == selected_category.casefold()
        ]

    if search_query:
        search_term = search_query.casefold()
        articles = [
            article for article in articles
            if search_term in article["title"].casefold()
            or search_term in article["category"].casefold()
            or search_term in article["content"].casefold()
        ]

    per_page = 6
    total_results = len(articles)
    total_pages = max(1, (total_results + per_page - 1) // per_page)
    page = max(1, request.args.get("page", 1, type=int))
    page = min(page, total_pages)
    start_index = (page - 1) * per_page
    page_articles = articles[start_index:start_index + per_page]

    return render_template(
        "home.html",
        articles=page_articles,
        page=page,
        total_pages=total_pages,
        total_results=total_results,
        categories=categories,
        search_query=search_query,
        selected_category=selected_category,
        total_articles=len(all_articles),
        featured_articles=(
            [article for article in all_articles if article["featured"]][:3]
            if not search_query and not selected_category else []
        )
    )


# Individual article page
@app.route("/article/<slug>")
def article(slug):
    article_file = next(
        (
            path for path in ARTICLES_DIR.glob("*.md")
            if path.stem == slug
        ),
        None
    )

    if article_file is None:
        abort(404)

    post = frontmatter.load(article_file)

    if not post.metadata.get("published", True):
        abort(404)

    content = markdown.markdown(
        post.content,
        extensions=["fenced_code"]
    )
    related_articles = [
        item for item in get_articles()
        if item["slug"] != slug
        and item["category"].casefold() == post.metadata.get("category", "General").casefold()
    ][:3]
    excerpt = post.metadata.get("excerpt", "").strip()
    if not excerpt:
        excerpt = " ".join(post.content.split())[:160]

    return render_template(
        "article.html",
        title=post.metadata.get("title", "Untitled"),
        date=post.metadata.get("date", ""),
        category=post.metadata.get("category", "General"),
        content=content,
        slug=slug,
        excerpt=excerpt,
        reading_time=estimate_reading_time(post.content),
        related_articles=related_articles,
        cover_image=post.metadata.get("cover_image", ""),
        book_url=post.metadata.get("book_url", ""),
        book_pdf=(
            f"book_pdfs/{slug}.pdf"
            if (BOOK_PDF_DIR / f"{slug}.pdf").is_file()
            else ""
        )
    )


# Download a PDF copy of a published article
@app.route("/article/<slug>/pdf")
def download_article_pdf(slug):
    article_file = ARTICLES_DIR / f"{slug}.md"

    if not article_file.is_file():
        abort(404)

    post = frontmatter.load(article_file)

    if not post.metadata.get("published", True):
        abort(404)

    pdf_file = create_article_pdf(
        title=post.metadata.get("title", "Untitled"),
        date=str(post.metadata.get("date", "")),
        category=post.metadata.get("category", "General"),
        content=post.content
    )

    return send_file(
        pdf_file,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"{slug}.pdf"
    )


# Admin login
@app.route("/admin/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if (
            username == app.config["ADMIN_USERNAME"]
            and check_password_hash(
                app.config["ADMIN_PASSWORD_HASH"],
                password
            )
        ):
            session.clear()
            session["admin_logged_in"] = True
            session.permanent = True

            return redirect(url_for("dashboard"))

        flash("Invalid username or password.")

    return render_template("admin/login.html")


# Admin dashboard
@app.route("/admin/dashboard")
@login_required
def dashboard():
    all_articles = get_all_articles()
    published_count = sum(article["published"] for article in all_articles)
    draft_count = len(all_articles) - published_count
    featured_count = sum(
        bool(article["featured"] and article["published"])
        for article in all_articles
    )

    search_query = request.args.get("q", "").strip()
    selected_status = request.args.get("status", "all").strip().lower()
    selected_category = request.args.get("category", "").strip()
    sort_by = request.args.get("sort", "newest").strip().lower()

    articles = all_articles

    if selected_status == "published":
        articles = [item for item in articles if item["published"]]
    elif selected_status == "draft":
        articles = [item for item in articles if not item["published"]]
    elif selected_status == "featured":
        articles = [item for item in articles if item["featured"]]

    if selected_category:
        articles = [
            item for item in articles
            if item["category"].casefold() == selected_category.casefold()
        ]

    if search_query:
        term = search_query.casefold()
        articles = [
            item for item in articles
            if term in item["title"].casefold()
            or term in item["category"].casefold()
            or term in item["excerpt"].casefold()
            or term in item["content"].casefold()
        ]

    if sort_by == "oldest":
        articles.sort(key=lambda item: item["date"])
    elif sort_by == "title":
        articles.sort(key=lambda item: item["title"].casefold())
    else:
        articles.sort(key=lambda item: item["date"], reverse=True)

    categories = sorted({item["category"] for item in all_articles})

    return render_template(
        "admin/dashboard.html",
        articles=articles,
        published_count=published_count,
        draft_count=draft_count,
        featured_count=featured_count,
        total_count=len(all_articles),
        categories=categories,
        search_query=search_query,
        selected_status=selected_status,
        selected_category=selected_category,
        sort_by=sort_by,
        result_count=len(articles)
    )


# Download a complete backup of articles and attached book PDFs
@app.route("/admin/backup")
@login_required
def download_backup():
    backup_buffer = BytesIO()

    with ZipFile(backup_buffer, "w", compression=ZIP_DEFLATED) as backup_zip:
        if ARTICLES_DIR.is_dir():
            for article_file in sorted(ARTICLES_DIR.glob("*.md")):
                backup_zip.write(article_file, arcname=f"articles/{article_file.name}")

        if BOOK_PDF_DIR.is_dir():
            for pdf_file in sorted(BOOK_PDF_DIR.glob("*.pdf")):
                backup_zip.write(pdf_file, arcname=f"book_pdfs/{pdf_file.name}")

        if COVER_IMAGE_DIR.is_dir():
            for image_file in sorted(COVER_IMAGE_DIR.iterdir()):
                if image_file.is_file():
                    backup_zip.write(image_file, arcname=f"cover_images/{image_file.name}")

        backup_zip.writestr(
            "BACKUP-INFO.txt",
            "Personal Blog content backup\n"
            "Contains article Markdown files (including drafts), attached book PDFs, and cover images.\n"
            "Keep this archive in a safe, private location.\n"
        )

    backup_buffer.seek(0)
    backup_name = datetime.now().strftime("personal-blog-backup-%Y%m%d-%H%M%S.zip")

    return send_file(
        backup_buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=backup_name
    )


# Add a new article
@app.route("/admin/articles/add", methods=["GET", "POST"])
@login_required
def add_article():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        date = request.form.get("date", "").strip()
        content = request.form.get("content", "").strip()
        category = request.form.get("category", "").strip() or "General"
        excerpt = request.form.get("excerpt", "").strip()[:300]
        featured = request.form.get("featured") == "on"
        published = request.form.get("published") == "on"
        book_url = request.form.get("book_url", "").strip()
        book_pdf = request.files.get("book_pdf")
        cover_image = request.files.get("cover_image")

        if not title or not date or not content:
            flash("Please fill in all required fields.")
            return render_template("admin/add_article.html")

        slug = secure_filename(title.lower().replace(" ", "-"))

        if not slug:
            flash("Please enter a valid article title.")
            return render_template("admin/add_article.html")

        article_file = ARTICLES_DIR / f"{slug}.md"

        if article_file.exists():
            flash("An article with this title already exists.")
            return render_template("admin/add_article.html")

        if not is_valid_book_url(book_url):
            flash("Please enter a valid official book URL beginning with http:// or https://.")
            return render_template("admin/add_article.html")

        if book_pdf and book_pdf.filename and not valid_book_pdf(book_pdf):
            flash("Please upload a valid PDF file.")
            return render_template("admin/add_article.html")

        if cover_image and cover_image.filename and not valid_cover_image(cover_image):
            flash("Please upload a JPEG, PNG, or WebP cover image no larger than 5 MB.")
            return render_template("admin/add_article.html")

        post = frontmatter.Post(
            content,
            title=title,
            date=date,
            category=category,
            published=published,
            excerpt=excerpt,
            featured=featured,
            cover_image="",
            book_url=book_url,
            book_pdf=f"{slug}.pdf" if book_pdf and book_pdf.filename else ""
        )

        frontmatter.dump(post, str(article_file))

        if book_pdf and book_pdf.filename:
            book_pdf.save(BOOK_PDF_DIR / f"{slug}.pdf")

        if cover_image and cover_image.filename:
            post.metadata["cover_image"] = save_cover_image(cover_image, slug)
            frontmatter.dump(post, str(article_file))

        flash("Article created successfully!")
        return redirect(url_for("dashboard"))

    return render_template("admin/add_article.html")


# Edit an existing article
@app.route("/admin/articles/<slug>/edit", methods=["GET", "POST"])
@login_required
def edit_article(slug):
    article_file = ARTICLES_DIR / f"{slug}.md"

    if not article_file.is_file():
        abort(404)

    post = frontmatter.load(article_file)

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        date = request.form.get("date", "").strip()
        category = request.form.get("category", "").strip() or "General"
        excerpt = request.form.get("excerpt", "").strip()[:300]
        featured = request.form.get("featured") == "on"
        content = request.form.get("content", "").strip()
        published = request.form.get("published") == "on"
        book_url = request.form.get("book_url", "").strip()
        book_pdf = request.files.get("book_pdf")
        cover_image = request.files.get("cover_image")

        if not title or not date or not content:
            flash("Please fill in all required fields.")
            return render_template(
                "admin/edit_article.html",
                article={
                    "slug": slug,
                    "title": title,
                    "date": date,
                    "category": category,
                    "excerpt": excerpt,
                    "featured": featured,
                    "content": content,
                    "published": published,
                    "book_url": book_url,
                    "book_pdf": post.metadata.get("book_pdf", "")
                }
            )

        if not is_valid_book_url(book_url):
            flash("Please enter a valid official book URL beginning with http:// or https://.")
            return redirect(url_for("edit_article", slug=slug))

        if book_pdf and book_pdf.filename and not valid_book_pdf(book_pdf):
            flash("Please upload a valid PDF file.")
            return redirect(url_for("edit_article", slug=slug))

        if cover_image and cover_image.filename and not valid_cover_image(cover_image):
            flash("Please upload a JPEG, PNG, or WebP cover image no larger than 5 MB.")
            return redirect(url_for("edit_article", slug=slug))

        post.metadata["title"] = title
        post.metadata["date"] = date
        post.metadata["category"] = category
        post.metadata["excerpt"] = excerpt
        post.metadata["featured"] = featured
        post.metadata["published"] = published
        post.metadata["book_url"] = book_url
        post.content = content

        if book_pdf and book_pdf.filename:
            book_pdf.save(BOOK_PDF_DIR / f"{slug}.pdf")
            post.metadata["book_pdf"] = f"{slug}.pdf"

        if cover_image and cover_image.filename:
            old_cover_image = post.metadata.get("cover_image", "")
            post.metadata["cover_image"] = save_cover_image(cover_image, slug)
            remove_cover_image(old_cover_image)

        frontmatter.dump(post, str(article_file))

        flash("Article updated successfully.")
        return redirect(url_for("dashboard"))

    article = {
        "slug": slug,
        "title": post.metadata.get("title", "Untitled"),
        "date": str(post.metadata.get("date", "")),
        "category": post.metadata.get("category", "General"),
        "excerpt": post.metadata.get("excerpt", ""),
        "featured": post.metadata.get("featured", False),
        "content": post.content,
        "published": post.metadata.get("published", True),
        "book_url": post.metadata.get("book_url", ""),
        "book_pdf": post.metadata.get("book_pdf", ""),
        "cover_image": post.metadata.get("cover_image", ""),
    }

    return render_template("admin/edit_article.html", article=article)


# Delete an article using POST so a normal page visit cannot delete it
@app.route("/admin/articles/<slug>/delete", methods=["POST"])
@login_required
def delete_article(slug):
    article_file = ARTICLES_DIR / f"{slug}.md"

    if not article_file.is_file():
        abort(404)

    post = frontmatter.load(article_file)
    article_file.unlink()

    book_pdf = BOOK_PDF_DIR / f"{slug}.pdf"
    if book_pdf.is_file():
        book_pdf.unlink()

    remove_cover_image(post.metadata.get("cover_image", ""))

    flash("Article deleted successfully.")
    return redirect(url_for("dashboard"))


# Admin logout
@app.route("/admin/logout", methods=["POST"])
@login_required
def logout():
    session.clear()

    return redirect(url_for("login"))


# Search-engine and feed endpoints
@app.route("/feed.xml")
def rss_feed():
    """Provide an RSS feed containing the latest published articles."""
    root = ET.Element("rss", version="2.0")
    channel = ET.SubElement(root, "channel")
    ET.SubElement(channel, "title").text = "My Personal Blog"
    ET.SubElement(channel, "link").text = request.url_root.rstrip("/")
    ET.SubElement(channel, "description").text = (
        "Articles about Christian growth, software engineering, books, "
        "and personal development."
    )

    for article_item in get_articles()[:20]:
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = article_item["title"]
        ET.SubElement(item, "link").text = request.url_root.rstrip("/") + url_for(
            "article", slug=article_item["slug"]
        )
        ET.SubElement(item, "guid").text = request.url_root.rstrip("/") + url_for(
            "article", slug=article_item["slug"]
        )
        ET.SubElement(item, "description").text = article_item["excerpt"] or ""
        if article_item["date"]:
            try:
                published_at = datetime.fromisoformat(article_item["date"])
                ET.SubElement(item, "pubDate").text = format_datetime(published_at)
            except ValueError:
                pass

    xml_content = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return Response(xml_content, mimetype="application/rss+xml")


@app.route("/sitemap.xml")
def sitemap():
    """List public URLs so search engines can discover published content."""
    root = ET.Element(
        "urlset",
        xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
    )
    public_urls = [url_for("home", _external=True)]
    public_urls.extend(
        url_for("article", slug=item["slug"], _external=True)
        for item in get_articles()
    )

    for public_url in public_urls:
        url_element = ET.SubElement(root, "url")
        ET.SubElement(url_element, "loc").text = public_url

    xml_content = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return Response(xml_content, mimetype="application/xml")


@app.route("/robots.txt")
def robots_txt():
    """Tell search crawlers which public sitemap to use."""
    content = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /admin/\n"
        f"Sitemap: {request.url_root.rstrip('/')}{url_for('sitemap')}\n"
    )
    return Response(content, mimetype="text/plain")


@app.after_request
def add_security_headers(response):
    """Apply baseline browser security headers to every response."""
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
    )
    return response


@app.errorhandler(404)
def page_not_found(error):
    return render_template("errors/404.html"), 404


@app.errorhandler(500)
def internal_server_error(error):
    return render_template("errors/500.html"), 500


# Start application
if __name__ == "__main__":
    app.run(debug=app.config.get("DEBUG", False))
