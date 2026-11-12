# Product Requirements Document (PRD)

## Project: Personal Blog

**Project Type:** Web Application  
**Difficulty:** Beginner  
**Programming Language:** Python  
**Framework:** Flask  
**Storage:** Local Filesystem  
**Content Format:** Markdown  
**Authentication:** Basic Admin Authentication  

---

## 1. Project Overview

The Personal Blog is a web application that allows an administrator to write, publish, edit, and delete articles on different topics.

The application will have two main sections: a public guest section and a protected administrator section.

Visitors can read published articles without logging in, while the administrator must authenticate before managing blog content.

## 2. Project Objectives

The objectives are to:

- Build a functional personal blogging platform.
- Allow visitors to read published articles.
- Provide an administrator dashboard for managing articles.
- Support Markdown formatting for article content.
- Store articles using the local filesystem.
- Implement authentication to protect administrative pages.
- Practise Python, Flask, filesystem operations, and web development.

## 3. Target Users

### Guest Users

Visitors who want to read articles published on the blog.

### Administrator

The blog owner responsible for creating, editing, publishing, and deleting articles.

## 4. Functional Requirements

### 4.1 Guest Section

**Home Page**
- Display all published articles.
- Show each article's title and publication date.
- Allow visitors to open individual articles.

**Article Page**
- Display the complete article.
- Render Markdown content as HTML.
- Display the publication date.
- Provide navigation back to the homepage.

### 4.2 Admin Section

**Login Page**
- Provide an administrator login form.
- Validate administrator credentials.
- Create an authenticated session after successful login.

**Dashboard**
- Display a list of published articles.
- Provide an option to create an article.
- Provide options to edit and delete articles.
- Provide a logout option.

**Add Article Page**
- Provide fields for article title, content, and publication date.
- Validate submitted information.
- Save the article as a Markdown file.

**Edit Article Page**
- Retrieve an existing article.
- Allow the administrator to update its title, content, and publication date.
- Save the updated article.

**Delete Article**
- Allow the administrator to delete an existing article.
- Require confirmation before deletion.

## 5. Non-Functional Requirements

- The application should be simple and beginner-friendly.
- The interface should be responsive and easy to navigate.
- Administrative pages must be protected from unauthorized access.
- User input must be validated.
- Articles must remain stored after restarting the application.
- Administrator passwords must not be stored as plain text.
- Secret credentials must be stored in environment variables.

## 6. Technology Stack

| Technology | Purpose |
|---|---|
| Python | Application logic |
| Flask | Web framework |
| HTML | Page structure |
| CSS | Website styling |
| Markdown | Article formatting |
| Filesystem | Article storage |
| Flask sessions | Authentication |
| Git and GitHub | Version control |

## 7. Data Storage

Each article will be stored as an individual Markdown file inside the `articles/` directory.

Each article will contain:

- Unique article identifier or filename.
- Article title.
- Article content.
- Publication date.

## 8. Security Requirements

- Only authenticated administrators can access admin functionality.
- Passwords must be securely hashed.
- Session secrets must be configured through environment variables.
- Article deletion and editing must be restricted to authenticated administrators.
- User-submitted content must be safely rendered.

## 9. Project Scope

### Included in Version 1

- Public homepage.
- Individual article pages.
- Administrator login and logout.
- Admin dashboard.
- Create articles.
- Edit articles.
- Delete articles.
- Markdown rendering.
- Filesystem-based article storage.

### Excluded from Version 1

- User registration.
- Visitor comments.
- Social media integration.
- Newsletter subscriptions.
- Multiple administrator accounts.
- Database integration.

## 10. Acceptance Criteria

The project will be considered successful when:

1. Visitors can access the homepage without logging in.
2. Visitors can open and read published articles.
3. Article content is correctly rendered from Markdown.
4. The administrator can log in with valid credentials.
5. Unauthorized users cannot access administrative functionality.
6. The administrator can create new articles.
7. The administrator can edit existing articles.
8. The administrator can delete articles.
9. Article data persists after restarting the application.
10. The application runs successfully without critical errors.

## 11. Development Milestones

1. Project setup and configuration.
2. Public homepage implementation.
3. Individual article implementation.
4. Markdown integration.
5. Filesystem article storage.
6. Administrator authentication.
7. Admin dashboard.
8. Article creation and editing.
9. Article deletion.
10. Testing, security review, and documentation.

## 12. Expected Outcome

A functional personal blogging platform where visitors can read published articles and the administrator can securely manage blog content through a simple web interface.

### Step to set up the app
``` py
python3 -m venv .venv
source .venv/bin/activate
pip install python-frontmatter
pip install markdown
pip install flask
pip install python-dotenv
touch .env
python -c "import secrets; print(secrets.token_hex(32))"
python -c 'from getpass import getpass; from werkzeug.security import generate_password_hash; print(generate_password_hash(getpass("Enter a new admin password: ")))'
```
