# Personal Blog

A Flask-based personal blog for articles about Christian growth, software engineering, and personal development.

## Reader experience features

The article list displays six items per page and preserves active search and category filters when readers move between pages. Article pages include a Share article action that uses the device share menu when available, otherwise copies the link or offers it for manual copying.

## Publishing features

The homepage supports featured articles and short article summaries. Article pages display an estimated reading time, show related articles from the same category, and include basic description and Open Graph metadata for sharing. In the admin editor, write a short summary and select **Feature this article** to highlight it on the homepage. Reading time is estimated at 200 words per minute.

## Complete book access

Each article can optionally include:

- An official publisher, author, or bookstore URL.
- A complete book PDF that the blog owner has the legal right to distribute.

To add book access:

1. Sign in through the **Admin Login** page.
2. Open the article in the admin dashboard and choose **Edit**, or create a new article.
3. Under **Complete book access**, enter the official book page URL.
4. Optionally upload an authorized PDF file (PDF format, maximum 25 MB).
5. Save the article.

The public article page displays a **Download complete book PDF** link when a PDF is attached, and a **Read or buy from official source** link when an official URL is provided.

Only upload PDFs that you own or are authorized to distribute. For copyrighted books without redistribution permission, provide an official purchase or reading link instead.

## Where uploaded PDFs are stored

Uploaded PDFs are saved in `static/book_pdfs/` using the article's slug as the filename. When running locally, add authorized PDFs to Git if you want them included in the repository and deployed with the application:

```bash
git add static/book_pdfs/
git commit -m "Add authorized book PDF files"
git push origin main
```

For a hosted deployment, make sure the hosting platform uses persistent file storage or an external file-storage service. Some hosting platforms erase files uploaded to the application filesystem when the app restarts or redeploys.

## Article PDF versus complete book PDF

The existing **Download PDF** button creates a PDF copy of the blog article. The separate complete-book section links to an uploaded authorized book PDF or an official external book page.


## Discovery, sharing, and reliability

The blog now provides additional publishing infrastructure:

- **RSS feed:** `/feed.xml` lists the latest 20 published articles for feed readers.
- **XML sitemap:** `/sitemap.xml` lists the homepage and published article pages for search engines.
- **Crawler rules:** `/robots.txt` points crawlers to the sitemap and keeps the admin URL space out of crawler discovery.
- **Browser security headers:** responses include content-type sniffing protection, clickjacking protection, a referrer policy, and a restrictive permissions policy.
- **Helpful error pages:** custom 404 and 500 pages match the site's design.

### Run the automated tests

Install the dependencies, then run:

```bash
python -m unittest discover -s tests -v
```

The route tests use temporary article files and do not modify your real blog posts.


## Admin dashboard and writing tools

The administrator dashboard supports:
- Search across article titles, categories, summaries, and body text.
- Filter by publication status (all, published, drafts, or featured).
- Filter by category and sort by newest, oldest, or title.
- Quick links to view, edit, and delete articles.

The article editor displays a live word count, an estimated reading time (based on 200 words per minute), and a character count for the article summary.

Dashboard and editor changes are covered by the automated test suite:

```bash
python -m unittest discover -s tests -v
```


## Admin security

The admin area uses Flask-WTF CSRF protection. Every form that changes data—including login, article creation, editing, deletion, and logout—must submit a valid CSRF token. Logout uses POST rather than GET so that visiting a URL cannot trigger a logout action.


### Administrator session settings

Admin sessions are configured to expire after 30 minutes. Session cookies use the HttpOnly and SameSite=Lax settings. For a production deployment served over HTTPS, set the following environment variable:

```env
SESSION_COOKIE_SECURE=true
```

Keep this setting false for ordinary local HTTP development; enabling it on an HTTP-only local server prevents the browser from sending the session cookie.


## Downloading a content backup

Administrators can select **Download backup** from the dashboard to create a ZIP archive containing:

- Every article Markdown file in `articles/`, including unpublished drafts.
- Every attached PDF in `static/book_pdfs/`.
- A short backup information file.

The backup is generated when requested and sent directly to the administrator's browser; it is not stored permanently on the server. Keep downloaded backups private because they can contain unpublished writing and licensed documents. This is a manual backup feature, not an automatic scheduled backup.

To verify the backup route and its access control, run:

```bash
python -m unittest discover -s tests -v
```
