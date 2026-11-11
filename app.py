
from pathlib import Path

import frontmatter
from flask import Flask, render_template

app = Flask(__name__)

# Locate the articles directory
ARTICLES_DIR = Path(__file__).parent / "articles"


def get_articles():
    articles = []

    # Find every Markdown file
    for article_file in ARTICLES_DIR.glob("*.md"):
        post = frontmatter.load(article_file)

        # Skip unpublished articles
        if not post.metadata.get("published", True):
            continue

        article = {
            "slug": article_file.stem,
            "title": post.metadata.get("title", "Untitled"),
            "date": str(post.metadata.get("date", "")),
        }

        articles.append(article)

    # Display newest articles first
    articles.sort(key=lambda article: article["date"], reverse=True)

    return articles


@app.route("/")
def home():
    articles = get_articles()
    return render_template("home.html", articles=articles)


if __name__ == "__main__":
    app.run(debug=True)
