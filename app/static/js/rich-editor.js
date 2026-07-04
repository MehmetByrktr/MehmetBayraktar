document.addEventListener("DOMContentLoaded", () => {
    const textareas = document.querySelectorAll("textarea.rich-editor");

    textareas.forEach((textarea, index) => {
        createRichEditor(textarea, index);
    });
});

function createRichEditor(textarea, index) {
    const shell = document.createElement("div");
    shell.className = "rich-editor-shell";

    const toolbar = document.createElement("div");
    toolbar.className = "rich-toolbar";
    toolbar.innerHTML = `
        <select class="format-select" title="Başlık tipi">
            <option value="p">Paragraf</option>
            <option value="h2">Başlık 2</option>
            <option value="h3">Başlık 3</option>
            <option value="h4">Başlık 4</option>
        </select>

        <button type="button" data-cmd="bold" title="Kalın"><b>B</b></button>
        <button type="button" data-cmd="italic" title="İtalik"><i>I</i></button>
        <button type="button" data-cmd="underline" title="Altı çizili"><u>U</u></button>

        <span class="toolbar-separator"></span>

        <button type="button" data-cmd="insertUnorderedList" title="Madde listesi">• Liste</button>
        <button type="button" data-cmd="insertOrderedList" title="Numaralı liste">1. Liste</button>
        <button type="button" data-action="quote" title="Alıntı">Alıntı</button>
        <button type="button" data-action="code" title="Kod bloğu">&lt;/&gt; Kod</button>

        <span class="toolbar-separator"></span>

        <button type="button" data-action="link" title="Link ekle">Link</button>
        <button type="button" data-action="image" title="Görsel ekle">Görsel</button>
        <button type="button" data-action="table" title="Tablo ekle">Tablo</button>

        <span class="toolbar-separator"></span>

        <button type="button" data-action="removeFormat" title="Biçimi temizle">Temizle</button>
        <button type="button" data-action="source" title="HTML kaynak">HTML</button>
    `;

    const editor = document.createElement("div");
    editor.className = "rich-editor-area";
    editor.contentEditable = "true";
    editor.dataset.editorIndex = index;
    editor.innerHTML = textarea.value.trim() || "<p>İçeriğini buraya yaz...</p>";

    const sourceHelp = document.createElement("div");
    sourceHelp.className = "rich-source-help";
    sourceHelp.textContent = "HTML kaynak modu açık. Tekrar HTML butonuna basınca görsel editöre döner.";

    textarea.parentNode.insertBefore(shell, textarea);
    shell.appendChild(toolbar);
    shell.appendChild(editor);
    shell.appendChild(sourceHelp);
    shell.appendChild(textarea);

    textarea.classList.add("rich-source");
    textarea.style.display = "none";
    sourceHelp.style.display = "none";

    const syncToTextarea = () => {
        textarea.value = editor.innerHTML.trim();
    };

    const syncToEditor = () => {
        editor.innerHTML = textarea.value.trim() || "<p>İçeriğini buraya yaz...</p>";
    };

    editor.addEventListener("input", syncToTextarea);
    editor.addEventListener("blur", syncToTextarea);

    toolbar.querySelector(".format-select").addEventListener("change", (event) => {
        focusEditor(editor);
        const tag = event.target.value;
        document.execCommand("formatBlock", false, tag);
        syncToTextarea();
    });

    toolbar.querySelectorAll("[data-cmd]").forEach(button => {
        button.addEventListener("click", () => {
            focusEditor(editor);
            document.execCommand(button.dataset.cmd, false, null);
            syncToTextarea();
        });
    });

    toolbar.querySelectorAll("[data-action]").forEach(button => {
        button.addEventListener("click", () => {
            const action = button.dataset.action;
            focusEditor(editor);

            if (action === "link") {
                const url = prompt("Link adresi:");
                if (url) {
                    document.execCommand("createLink", false, url);
                }
            }

            if (action === "image") {
                const url = prompt("Görsel URL adresi:");
                if (url) {
                    const alt = prompt("Görsel açıklaması:", "") || "";
                    document.execCommand("insertHTML", false, `<img src="${escapeAttr(url)}" alt="${escapeAttr(alt)}">`);
                }
            }

            if (action === "table") {
                const rows = Math.max(1, parseInt(prompt("Satır sayısı:", "3") || "3", 10));
                const cols = Math.max(1, parseInt(prompt("Sütun sayısı:", "3") || "3", 10));
                document.execCommand("insertHTML", false, buildTable(rows, cols));
            }

            if (action === "quote") {
                const selected = getSelectionHtml();
                document.execCommand("insertHTML", false, `<blockquote>${selected || "Alıntı metni..."}</blockquote>`);
            }

            if (action === "code") {
                const selected = getSelectionText();
                const code = selected || prompt("Kod bloğu:", "print('Merhaba')") || "";
                document.execCommand("insertHTML", false, `<pre><code>${escapeHtml(code)}</code></pre><p><br></p>`);
            }

            if (action === "removeFormat") {
                document.execCommand("removeFormat", false, null);
            }

            if (action === "source") {
                const sourceVisible = textarea.style.display !== "none";

                if (sourceVisible) {
                    syncToEditor();
                    textarea.style.display = "none";
                    editor.style.display = "block";
                    sourceHelp.style.display = "none";
                } else {
                    syncToTextarea();
                    textarea.style.display = "block";
                    editor.style.display = "none";
                    sourceHelp.style.display = "block";
                }
            }

            syncToTextarea();
        });
    });

    const form = textarea.closest("form");
    if (form) {
        form.addEventListener("submit", () => {
            if (textarea.style.display !== "none") {
                syncToEditor();
            }
            syncToTextarea();
        });
    }
}

function focusEditor(editor) {
    editor.focus();
}

function getSelectionHtml() {
    const selection = window.getSelection();
    if (!selection.rangeCount) return "";
    const container = document.createElement("div");
    for (let i = 0; i < selection.rangeCount; i++) {
        container.appendChild(selection.getRangeAt(i).cloneContents());
    }
    return container.innerHTML;
}

function getSelectionText() {
    const selection = window.getSelection();
    return selection ? selection.toString() : "";
}

function buildTable(rows, cols) {
    let html = "<table><tbody>";
    for (let r = 0; r < rows; r++) {
        html += "<tr>";
        for (let c = 0; c < cols; c++) {
            html += r === 0 ? "<th>Başlık</th>" : "<td>İçerik</td>";
        }
        html += "</tr>";
    }
    html += "</tbody></table><p><br></p>";
    return html;
}

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");
}

function escapeAttr(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll('"', "&quot;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");
}


document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".live-image-input").forEach(input => {
        input.addEventListener("change", () => {
            const targetId = input.dataset.previewTarget;
            const target = document.getElementById(targetId);
            const file = input.files && input.files[0];

            if (!target || !file) return;

            const reader = new FileReader();
            reader.onload = event => {
                target.src = event.target.result;
                target.style.display = "block";
            };
            reader.readAsDataURL(file);
        });
    });
});


document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-confirm]").forEach(button => {
        button.addEventListener("click", event => {
            const message = button.getAttribute("data-confirm") || "Bu işlemi yapmak istediğine emin misin?";
            if (!window.confirm(message)) {
                event.preventDefault();
            }
        });
    });
});
