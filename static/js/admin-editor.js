document.addEventListener("DOMContentLoaded", () => {
    const contentField = document.getElementById("content");
    const excerptField = document.getElementById("excerpt");
    const wordCount = document.getElementById("word-count");
    const readingEstimate = document.getElementById("reading-estimate");
    const excerptCount = document.getElementById("excerpt-count");

    function updateWritingStats() {
        if (!contentField) return;
        const words = contentField.value.trim().split(/\s+/).filter(Boolean).length;
        if (wordCount) wordCount.textContent = words;
        if (readingEstimate) readingEstimate.textContent = Math.max(1, Math.ceil(words / 200));
    }

    function updateExcerptCount() {
        if (excerptField && excerptCount) excerptCount.textContent = excerptField.value.length;
    }

    if (contentField) contentField.addEventListener("input", updateWritingStats);
    if (excerptField) excerptField.addEventListener("input", updateExcerptCount);
    updateWritingStats();
    updateExcerptCount();
});
