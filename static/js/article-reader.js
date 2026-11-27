document.addEventListener("DOMContentLoaded", () => {
    const article = document.querySelector(".full-article");
    const content = document.querySelector("#article-content");
    const progressBar = document.querySelector("#reading-progress-bar");
    const toc = document.querySelector("#article-toc");
    const tocList = document.querySelector("#article-toc-list");

    if (!article || !content) return;

    // Build a navigable contents list when the article has enough sections.
    const headings = Array.from(content.querySelectorAll("h2, h3"));
    if (headings.length >= 3 && toc && tocList) {
        headings.forEach((heading, index) => {
            if (!heading.id) {
                heading.id = `article-section-${index + 1}`;
            }

            const item = document.createElement("li");
            const link = document.createElement("a");
            link.href = `#${heading.id}`;
            link.textContent = heading.textContent.trim();
            link.dataset.headingId = heading.id;
            item.appendChild(link);
            tocList.appendChild(item);
        });

        toc.hidden = false;

        if ("IntersectionObserver" in window) {
            const links = tocList.querySelectorAll("a");
            const observer = new IntersectionObserver((entries) => {
                entries.forEach((entry) => {
                    if (!entry.isIntersecting) return;
                    links.forEach((link) => {
                        const active = link.dataset.headingId === entry.target.id;
                        link.classList.toggle("is-active", active);
                        if (active) link.setAttribute("aria-current", "location");
                        else link.removeAttribute("aria-current");
                    });
                });
            }, { rootMargin: "-15% 0px -70% 0px" });

            headings.forEach((heading) => observer.observe(heading));
        }
    }

    // Update the reading indicator without repeatedly recalculating during scroll.
    let ticking = false;
    const updateProgress = () => {
        const scrollableHeight = document.documentElement.scrollHeight - window.innerHeight;
        const progress = scrollableHeight > 0
            ? (window.scrollY / scrollableHeight) * 100
            : 0;

        if (progressBar) {
            progressBar.style.width = `${Math.min(100, Math.max(0, progress))}%`;
        }
        ticking = false;
    };

    window.addEventListener("scroll", () => {
        if (!ticking) {
            window.requestAnimationFrame(updateProgress);
            ticking = true;
        }
    }, { passive: true });
    window.addEventListener("resize", updateProgress);
    updateProgress();

    // Share using the native device menu when available, otherwise copy the link.
    const shareButton = document.querySelector(".share-article-button");
    if (shareButton) {
        shareButton.addEventListener("click", async () => {
            const shareData = {
                title: shareButton.dataset.shareTitle,
                url: shareButton.dataset.shareUrl
            };

            try {
                if (navigator.share) {
                    await navigator.share(shareData);
                } else if (navigator.clipboard) {
                    await navigator.clipboard.writeText(shareData.url);
                    shareButton.textContent = "Link copied";
                } else {
                    window.prompt("Copy this article link:", shareData.url);
                }
            } catch (error) {
                if (error.name !== "AbortError") {
                    window.prompt("Copy this article link:", shareData.url);
                }
            }
        });
    }
});
