function renderMath(text, mathReady) {
    if (!text) return "";

    return text.replace(/\$(.+?)\$/g, (match, expr) => {
        if (mathReady) {
            return match;
        }
        return `<code>${expr}</code>`;
    });
}


function escapeHtml(value) {
    return value
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/'/g, "&#39;");
}

export function renderMarkdown(text, mathReady) {
    if (!text) return "";

    const protectedParts = [];

    function protect(value) {
        const index = protectedParts.length;
        protectedParts.push(value);
        return `\uE000${index}\uE001`;
    }

    // Protect fenced code blocks first.
    // Everything inside a fenced block is treated literally.
    text = text.replace(/```(?:[^\n`]*)\n([\s\S]*?)```/g, (_, content) =>
        protect(`<pre><code>${escapeHtml(content)}</code></pre>`),
    );

    // Protect inline code.
    // Everything between backticks is treated literally.
    text = text.replace(/`([^`]*?)`/g, (_, content) =>
        protect(`<code>${escapeHtml(content)}</code>`),
    );

    // Protect math from Markdown processing.
    text = text.replace(/\$\$[\s\S]*?\$\$/g, protect);
    text = text.replace(/\$(?!\$)[\s\S]*?\$(?!\$)/g, protect);

    // Escape things that look like HTML tags but aren't actually
    // part of a valid HTML element.
    const voidElements = new Set([
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    ]);

    text = text.replace(
        /<\/?(\p{L}[\p{L}\p{N}-]*)(?:\s[^>]*)?>/gu,
        (match, tagName, offset, wholeText) => {
            const tag = tagName.toLowerCase();

            // Closing tags are valid if they appear.
            if (match.startsWith("</")) {
                return match;
            }

            // Self-closing tags are valid.
            if (/\/>$/.test(match)) {
                return match;
            }

            // Void HTML elements don't need a closing tag.
            if (voidElements.has(tag)) {
                return match;
            }

            // For normal elements, require a matching closing tag.
            const closingTag = new RegExp(`</${tag}\\s*>`, "iu");

            if (closingTag.test(wholeText.slice(offset + match.length))) {
                return match;
            }

            // Otherwise, treat it as literal text.
            return match.replace(/</g, "&lt;").replace(/>/g, "&gt;");
        },
    );

    // Markdown.
    // Code spans and code blocks are already protected.
    text = text
        .replace(/\*\*(.*?)\*\*/g, "<b>$1</b>")
        .replace(/\*(.*?)\*/g, "<i>$1</i>");

    // Restore protected content.
    text = text.replace(
        /\uE000(\d+)\uE001/g,
        (_, index) => protectedParts[Number(index)],
    );

    return renderMath(text, mathReady);
}


/*
 * Removes <p> and <br> HTML tags from formatted text.
 * Other HTML and Markdown content is preserved.
 */
export function toMarkdown(text) {
    if (!text) return "";

    // Apply custom markdown rendering rules to preserve protected items
    text = renderMarkdown(text, true);

    // fallback for if CDN is not allowed or offline
    const container = document.createElement("div");
    container.innerHTML = text;


    function convert(node) {
        if (node.nodeType === Node.TEXT_NODE) {
            return node.textContent;
        }

        if (node.nodeType !== Node.ELEMENT_NODE) {
            return "";
        }

        const tag = node.tagName.toLowerCase();

        const content = [...node.childNodes]
            .map(convert)
            .join("");

        switch (tag) {
            // Text formatting
            case "strong":
            case "b":
                return `**${content}**`;

            case "em":
            case "i":
                return `*${content}*`;

            case "u":
                return `<u>${content}</u>`;

            case "s":
            case "strike":
            case "del":
                return `~~${content}~~`;

            // Paragraphs
            case "p":
                return `${content}\n\n`;

            case "br":
                return "\n";

            case "hr":
                return "\n\n---\n\n";

            // Links
            case "a": {
                const href = node.getAttribute("href");

                // A literal <a> with no content/href.
                if (!href && !content.trim()) {
                    return "<a>";
                }

                if (!href) {
                    return content;
                }

                const title = node.getAttribute("title");
                const titlePart = title ? ` "${title}"` : "";

                return `[${content}](${href}${titlePart})`;
            }

            // Images
            case "img": {
                const src = node.getAttribute("src");

                if (!src) {
                    return "<img>";
                }

                const alt = node.getAttribute("alt") || "";
                const title = node.getAttribute("title");
                const titlePart = title ? ` "${title}"` : "";

                return `![${alt}](${src}${titlePart})`;
            }

            // Code
            case "code":
                if (node.parentElement?.tagName.toLowerCase() === "pre") {
                    return content;
                }

                return `\`${content.replace(/`/g, "\\`")}\``;

            case "pre": {
                const code = node.querySelector(":scope > code");
                const value = code ? code.textContent : node.textContent;

                return `\n\n\`\`\`\n${value.replace(/\n+$/, "")}\n\`\`\`\n\n`;
            }

            // Lists
            case "ul":
                return (
                    "\n\n" +
                    [...node.children]
                        .filter(
                            (child) =>
                                child.tagName.toLowerCase() === "li",
                        )
                        .map((child) => `- ${convert(child).trim()}`)
                        .join("\n") +
                    "\n\n"
                );

            case "ol":
                return (
                    "\n\n" +
                    [...node.children]
                        .filter(
                            (child) =>
                                child.tagName.toLowerCase() === "li",
                        )
                        .map(
                            (child, index) =>
                                `${index + 1}. ${convert(child).trim()}`,
                        )
                        .join("\n") +
                    "\n\n"
                );

            case "li":
                return content;

            // Tables
            case "table":
                return convertTable(node);

            // Blockquote
            case "blockquote":
                return (
                    "\n\n" +
                    content
                        .trim()
                        .split("\n")
                        .map((line) => `> ${line}`)
                        .join("\n") +
                    "\n\n"
                );

            // Headings
            case "h1":
            case "h2":
            case "h3":
            case "h4":
            case "h5":
            case "h6": {
                const level = Number(tag[1]);
                return `\n\n${"#".repeat(level)} ${content.trim()}\n\n`;
            }

            // Media with no Markdown equivalent
            case "video":
            case "audio":
            case "iframe":
                return node.outerHTML;

            // Other elements: preserve their contents
            default:
                return content;
        }
    }

    function convertTable(table) {
        const rows = [...table.querySelectorAll(":scope > tbody > tr, :scope > tr")];

        if (!rows.length) {
            return "";
        }

        const data = rows.map((row) =>
            [...row.children]
                .filter((cell) =>
                    ["th", "td"].includes(cell.tagName.toLowerCase()),
                )
                .map((cell) =>
                    convert(cell)
                        .trim()
                        .replace(/\|/g, "\\|")
                        .replace(/\n+/g, " "),
                ),
        );

        if (!data.length) {
            return "";
        }

        const columnCount = Math.max(...data.map((row) => row.length));

        const header = Array.from(
            { length: columnCount },
            (_, i) => data[0][i] || "",
        );

        const separator = Array.from(
            { length: columnCount },
            () => "---",
        );

        const body = data.slice(1).map((row) =>
            Array.from(
                { length: columnCount },
                (_, i) => row[i] || "",
            ),
        );

        return [
            "",
            `| ${header.join(" | ")} |`,
            `| ${separator.join(" | ")} |`,
            ...body.map((row) => `| ${row.join(" | ")} |`),
            "",
        ].join("\n");
    }

    return [...container.childNodes]
        .map(convert)
        .join("")
        .replace(/[ \t]+\n/g, "\n")
        .replace(/\n{3,}/g, "\n\n")
        .trim();
}
