
from pathlib import Path
from functools import wraps

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
    flash
)

from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename


app = Flask(__name__)

# Load application configuration
app.config.from_object("config.Config")


# Locate the articles directory
ARTICLES_DIR = Path(__file__).parent / "articles"


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

    return render_template(
        "home.html",
        articles=articles,
        categories=categories,
        search_query=search_query,
        selected_category=selected_category,
        total_articles=len(all_articles)
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

    return render_template(
        "article.html",
        title=post.metadata.get("title", "Untitled"),
        date=post.metadata.get("date", ""),
        category=post.metadata.get("category", "General"),
        content=content
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

    return render_template(
        "admin/dashboard.html",
        articles=articles,
        published_count=published_count,
        draft_count=draft_count,
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
        published = request.form.get("published") == "on"

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

        post = frontmatter.Post(
            content,
            title=title,
            date=date,
            category=category,
            published=published
        )

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
        content = request.form.get("content", "").strip()
        published = request.form.get("published") == "on"

        if not title or not date or not content:
            flash("Please fill in all required fields.")
            return render_template(
                "admin/edit_article.html",
                article={
                    "slug": slug,
                    "title": title,
                    "date": date,
                    "category": category,
                    "content": content,
                    "published": published
                }
            )

        post.metadata["title"] = title
        post.metadata["date"] = date
        post.metadata["category"] = category
        post.metadata["published"] = published
        post.content = content
        frontmatter.dump(post, str(article_file))

        flash("Article updated successfully.")
        return redirect(url_for("dashboard"))

    article = {
        "slug": slug,
        "title": post.metadata.get("title", "Untitled"),
        "date": str(post.metadata.get("date", "")),
        "category": post.metadata.get("category", "General"),
        "content": post.content,
        "published": post.metadata.get("published", True),
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
