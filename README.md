# Personal Blog

A Flask-based personal blog for articles about Christian growth, software engineering, and personal development.

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
