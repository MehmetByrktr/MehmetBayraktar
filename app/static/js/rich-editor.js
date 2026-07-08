document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("textarea.rich-editor").forEach((textarea, index) => {
        createRichEditor(textarea, index);
    });

    setupLiveImagePreview();
    setupConfirmButtons();
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

        <select class="font-select" title="Font tipi">
            <option value="">Font</option>
            <option value="Inter, Arial, sans-serif">Inter</option>
            <option value="Arial, sans-serif">Arial</option>
            <option value="Georgia, serif">Georgia</option>
            <option value="'Times New Roman', serif">Times New Roman</option>
            <option value="'Courier New', monospace">Courier New</option>
        </select>

        <select class="font-size-select" title="Font boyutu">
            <option value="">Boyut</option>
            <option value="0.85rem">Küçük</option>
            <option value="1rem">Normal</option>
            <option value="1.18rem">Büyük</option>
            <option value="1.45rem">Başlık</option>
        </select>

        <label class="color-tool" title="Yazı rengi">A <input type="color" class="text-color-input" value="#f4f2ec"></label>
        <label class="color-tool" title="Arka plan rengi">BG <input type="color" class="bg-color-input" value="#2a2c2c"></label>

        <span class="toolbar-separator"></span>

        <button type="button" data-cmd="bold" title="Kalın"><b>B</b></button>
        <button type="button" data-cmd="italic" title="İtalik"><i>I</i></button>
        <button type="button" data-cmd="underline" title="Altı çizili"><u>U</u></button>
        <button type="button" data-cmd="strikeThrough" title="Üstü çizili"><s>S</s></button>

        <span class="toolbar-separator"></span>

        <button type="button" data-cmd="justifyLeft" title="Sola hizala">Sol</button>
        <button type="button" data-cmd="justifyCenter" title="Ortala">Orta</button>
        <button type="button" data-cmd="justifyRight" title="Sağa hizala">Sağ</button>

        <span class="toolbar-separator"></span>

        <button type="button" data-cmd="insertUnorderedList" title="Madde listesi">• Liste</button>
        <button type="button" data-cmd="insertOrderedList" title="Numaralı liste">1. Liste</button>
        <button type="button" data-action="quote" title="Alıntı">Alıntı</button>
        <button type="button" data-action="code" title="Kod bloğu">&lt;/&gt; Kod</button>
        <button type="button" data-action="hr" title="Ayırıcı çizgi">Çizgi</button>

        <span class="toolbar-separator"></span>

        <button type="button" data-action="link" title="Link ekle">Link</button>
        <button type="button" data-action="image" title="Görsel ekle">Görsel</button>
        <button type="button" data-action="table" title="Tablo ekle">Tablo</button>

        <span class="toolbar-separator"></span>

        <button type="button" data-cmd="undo" title="Geri al">↶</button>
        <button type="button" data-cmd="redo" title="İleri al">↷</button>
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

    const command = (cmd, value = null) => {
        focusEditor(editor);
        document.execCommand("styleWithCSS", false, true);
        document.execCommand(cmd, false, value);
        syncToTextarea();
    };

    toolbar.querySelector(".format-select").addEventListener("change", event => {
        command("formatBlock", event.target.value);
    });

    toolbar.querySelector(".font-select").addEventListener("change", event => {
        const value = event.target.value;
        if (!value) return;
        applyInlineStyle(editor, { "font-family": value });
        event.target.value = "";
        syncToTextarea();
    });

    toolbar.querySelector(".font-size-select").addEventListener("change", event => {
        const value = event.target.value;
        if (!value) return;
        applyInlineStyle(editor, { "font-size": value });
        event.target.value = "";
        syncToTextarea();
    });

    toolbar.querySelector(".text-color-input").addEventListener("input", event => {
        command("foreColor", event.target.value);
    });

    toolbar.querySelector(".bg-color-input").addEventListener("input", event => {
        command("hiliteColor", event.target.value);
    });

    toolbar.querySelectorAll("[data-cmd]").forEach(button => {
        button.addEventListener("click", () => command(button.dataset.cmd));
    });

    toolbar.querySelectorAll("[data-action]").forEach(button => {
        button.addEventListener("click", () => {
            const action = button.dataset.action;
            focusEditor(editor);

            if (action === "link") {
                const url = prompt("Link adresi:");
                if (url && isSafeUrl(url)) {
                    document.execCommand("createLink", false, url);
                    setLinkSafety();
                }
            }

            if (action === "image") {
                const url = prompt("Görsel URL adresi:");
                if (url && isSafeUrl(url)) {
                    const alt = prompt("Görsel açıklaması:", "") || "";
                    document.execCommand("insertHTML", false, `<img src="${escapeAttr(url)}" alt="${escapeAttr(alt)}" loading="lazy">`);
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

            if (action === "hr") {
                document.execCommand("insertHTML", false, "<hr><p><br></p>");
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
                    button.classList.remove("is-active");
                } else {
                    syncToTextarea();
                    textarea.style.display = "block";
                    editor.style.display = "none";
                    sourceHelp.style.display = "block";
                    button.classList.add("is-active");
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

function applyInlineStyle(editor, styles) {
    focusEditor(editor);

    const selected = getSelectionHtml();
    const text = getSelectionText();
    if (!selected && !text) return;

    const styleText = Object.entries(styles)
        .map(([key, value]) => `${key}: ${escapeAttr(value)}`)
        .join("; ");

    document.execCommand("insertHTML", false, `<span style="${styleText}">${selected || escapeHtml(text)}</span>`);
}

function setLinkSafety() {
    document.querySelectorAll(".rich-editor-area a").forEach(link => {
        link.setAttribute("rel", "noopener noreferrer");
        if (link.href.startsWith("http")) {
            link.setAttribute("target", "_blank");
        }
    });
}

function isSafeUrl(value) {
    return /^(https?:\/\/|mailto:)/i.test(String(value).trim());
}

function getSelectionHtml() {
    const selection = window.getSelection();
    if (!selection || !selection.rangeCount) return "";
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

function setupLiveImagePreview() {
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
}

function setupConfirmButtons() {
    document.querySelectorAll("[data-confirm]").forEach(button => {
        button.addEventListener("click", event => {
            const message = button.getAttribute("data-confirm") || "Bu işlemi yapmak istediğine emin misin?";
            if (!window.confirm(message)) {
                event.preventDefault();
            }
        });
    });
}
