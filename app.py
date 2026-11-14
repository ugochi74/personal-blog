
from pathlib import Path
from functools import wraps
from urllib.parse import urlparse

import frontmatter
import markdown

from flask import (
    Flask,
    render_template,
    abort,
    request,
    redirect,
    url_for,
    session,
    flash,
    send_file
)

from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename

from pdf_generator import create_article_pdf


app = Flask(__name__)

# Load application configuration
app.config.from_object("config.Config")


# Locate the articles directory
ARTICLES_DIR = Path(__file__).parent / "articles"
BOOK_PDF_DIR = Path(__file__).parent / "static" / "book_pdfs"
BOOK_PDF_DIR.mkdir(parents=True, exist_ok=True)
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

            return redirect(url_for("dashboard"))

        flash("Invalid username or password.")

    return render_template("admin/login.html")


# Admin dashboard
@app.route("/admin/dashboard")
@login_required
def dashboard():
    articles = get_all_articles()
    published_count = sum(article["published"] for article in articles)
    draft_count = len(articles) - published_count
    featured_count = sum(bool(article["featured"] and article["published"]) for article in articles)

    return render_template(
        "admin/dashboard.html",
        articles=articles,
        published_count=published_count,
        draft_count=draft_count,
        featured_count=featured_count,
        total_count=len(articles)
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

        post = frontmatter.Post(
            content,
            title=title,
            date=date,
            category=category,
            published=published,
            excerpt=excerpt,
            featured=featured,
            book_url=book_url,
            book_pdf=f"{slug}.pdf" if book_pdf and book_pdf.filename else ""
        )

        frontmatter.dump(post, str(article_file))

        if book_pdf and book_pdf.filename:
            book_pdf.save(BOOK_PDF_DIR / f"{slug}.pdf")

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
    }

    return render_template("admin/edit_article.html", article=article)


# Delete an article using POST so a normal page visit cannot delete it
@app.route("/admin/articles/<slug>/delete", methods=["POST"])
@login_required
def delete_article(slug):
    article_file = ARTICLES_DIR / f"{slug}.md"

    if not article_file.is_file():
        abort(404)

    article_file.unlink()

    book_pdf = BOOK_PDF_DIR / f"{slug}.pdf"
    if book_pdf.is_file():
        book_pdf.unlink()

    flash("Article deleted successfully.")
    return redirect(url_for("dashboard"))


# Admin logout
@app.route("/admin/logout")
@login_required
def logout():
    session.clear()

    return redirect(url_for("login"))


# Start application
if __name__ == "__main__":
    app.run(debug=True)
