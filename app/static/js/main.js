// V23: Animated dark/light theme toggle
const root = document.documentElement;
const storedTheme = (() => {
    try { return localStorage.getItem("theme"); } catch (e) { return null; }
})();
const initialTheme = storedTheme === "light" || storedTheme === "dark" ? storedTheme : "dark";
root.setAttribute("data-theme", initialTheme);

function updateThemeToggleLabels() {
    document.querySelectorAll(".theme-toggle").forEach(button => {
        const isLight = root.getAttribute("data-theme") === "light";
        button.classList.toggle("is-light", isLight);
        button.setAttribute("aria-label", isLight ? "Koyu temaya geç" : "Açık temaya geç");
        button.setAttribute("title", isLight ? "Koyu temaya geç" : "Açık temaya geç");
    });
}

function setupThemeToggles() {
    updateThemeToggleLabels();
    document.querySelectorAll(".theme-toggle").forEach(button => {
        button.addEventListener("click", () => {
            const next = root.getAttribute("data-theme") === "light" ? "dark" : "light";
            root.setAttribute("data-theme", next);
            try { localStorage.setItem("theme", next); } catch (e) {}
            updateThemeToggleLabels();
        });
    });
}

// V11: İçindekiler, kod renklendirme, beğeni
document.addEventListener("DOMContentLoaded", () => {
    setupThemeToggles();
    buildArticleToc();
    enhanceCodeBlocks();
    setupLikeButtons();
    setupConfirmActions();
    setupMessageDialogs();
});

function setupConfirmActions() {
    document.querySelectorAll("[data-confirm]").forEach(element => {
        element.addEventListener("click", event => {
            const message = element.getAttribute("data-confirm") || "Bu işlemi yapmak istediğine emin misin?";
            if (!window.confirm(message)) {
                event.preventDefault();
            }
        });
    });
}

function slugifyHeading(text) {
    return text
        .toString()
        .toLowerCase()
        .trim()
        .replaceAll("ı", "i")
        .replaceAll("ğ", "g")
        .replaceAll("ü", "u")
        .replaceAll("ş", "s")
        .replaceAll("ö", "o")
        .replaceAll("ç", "c")
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "");
}

function buildArticleToc() {
    const content = document.querySelector(".article-content");
    const toc = document.querySelector("[data-toc]");
    const tocList = document.querySelector("[data-toc-list]");

    if (!content || !toc || !tocList) return;

    const headings = Array.from(content.querySelectorAll("h2, h3"));
    if (headings.length < 2) {
        toc.style.display = "none";
        return;
    }

    const used = new Set();

    headings.forEach((heading, index) => {
        let id = heading.id || slugifyHeading(heading.textContent) || `baslik-${index + 1}`;
        let uniqueId = id;
        let counter = 2;

        while (used.has(uniqueId)) {
            uniqueId = `${id}-${counter}`;
            counter++;
        }

        used.add(uniqueId);
        heading.id = uniqueId;

        const link = document.createElement("a");
        link.href = `#${uniqueId}`;
        link.textContent = heading.textContent;
        link.className = heading.tagName.toLowerCase() === "h3" ? "toc-subitem" : "";
        tocList.appendChild(link);
    });
}

function enhanceCodeBlocks() {
    document.querySelectorAll(".rich-content pre code, .article-content pre code").forEach(code => {
        const raw = code.textContent;
        code.innerHTML = simpleHighlight(raw);

        const pre = code.closest("pre");
        if (pre && !pre.querySelector(".copy-code-btn")) {
            const copy = document.createElement("button");
            copy.className = "copy-code-btn";
            copy.type = "button";
            copy.textContent = "Kopyala";
            copy.addEventListener("click", async () => {
                try {
                    await navigator.clipboard.writeText(raw);
                    copy.textContent = "Kopyalandı";
                    setTimeout(() => copy.textContent = "Kopyala", 1200);
                } catch {
                    copy.textContent = "Kopyalanamadı";
                    setTimeout(() => copy.textContent = "Kopyala", 1200);
                }
            });
            pre.appendChild(copy);
        }
    });
}

function simpleHighlight(value) {
    let html = value
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");

    html = html.replace(/("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/g, '<span class="code-string">$1</span>');
    html = html.replace(/\b(def|class|return|if|else|elif|for|while|import|from|as|try|except|with|lambda|True|False|None|const|let|var|function|new|await|async|public|private|void|int|float|double|String)\b/g, '<span class="code-keyword">$1</span>');
    html = html.replace(/\b(\d+(?:\.\d+)?)\b/g, '<span class="code-number">$1</span>');
    html = html.replace(/(#.*)$/gm, '<span class="code-comment">$1</span>');

    return html;
}

function setupLikeButtons() {
    document.querySelectorAll(".like-button").forEach(button => {
        button.addEventListener("click", async () => {
            const url = button.dataset.likeUrl;
            if (!url || button.dataset.loading === "1") return;

            button.dataset.loading = "1";

            try {
                const response = await fetch(url, { method: "POST" });
                const data = await response.json();

                if (data.ok) {
                    document.querySelectorAll("[data-like-count]").forEach(target => {
                        target.textContent = data.likes;
                    });

                    button.classList.toggle("liked", Boolean(data.liked));

                    const countSpan = button.querySelector("[data-like-count]");
                    if (countSpan) {
                        const label = data.liked ? "Beğenildi" : "Beğen";
                        button.firstChild.textContent = `${label} `;
                    }
                }
            } finally {
                button.dataset.loading = "0";
            }
        });
    });
}


function setupMessageDialogs() {
    document.querySelectorAll("[data-open-message]").forEach(button => {
        button.addEventListener("click", () => {
            const id = button.getAttribute("data-open-message");
            const dialog = document.getElementById(`message-dialog-${id}`);
            if (!dialog) return;

            if (typeof dialog.showModal === "function") {
                dialog.showModal();
            } else {
                dialog.setAttribute("open", "open");
            }
        });
    });

    document.querySelectorAll("[data-close-message]").forEach(button => {
        button.addEventListener("click", () => {
            const id = button.getAttribute("data-close-message");
            const dialog = document.getElementById(`message-dialog-${id}`);
            if (!dialog) return;
            dialog.close();
        });
    });

    document.querySelectorAll(".message-dialog").forEach(dialog => {
        dialog.addEventListener("click", event => {
            const rect = dialog.getBoundingClientRect();
            const clickedBackdrop =
                event.clientX < rect.left ||
                event.clientX > rect.right ||
                event.clientY < rect.top ||
                event.clientY > rect.bottom;

            if (clickedBackdrop) {
                dialog.close();
            }
        });
    });
}
