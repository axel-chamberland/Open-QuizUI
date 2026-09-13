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

