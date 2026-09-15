import { describe, it, expect } from "vitest";
import { renderMarkdown, toMarkdown } from "../frontend/src/shared/markdown.js";

describe("renderMarkdown", () => {
  it("renders bold and italic Markdown", () => {
    expect(renderMarkdown("**bold** and *italic*", true)).toBe(
      "<b>bold</b> and <i>italic</i>",
    );
  });

  it("protects math from Markdown processing", () => {
    expect(renderMarkdown("$**x**$", true)).toBe("$**x**$");
  });

  it("renders math as code when math is not ready", () => {
    expect(renderMarkdown("$x^2$", false)).toBe("<code>x^2</code>");
  });

  it("preserves valid HTML", () => {
    expect(renderMarkdown("<b>hello</b>", true)).toBe("<b>hello</b>");
  });

  it("escapes an unmatched HTML tag", () => {
    expect(renderMarkdown("<custom>", true)).toBe("&lt;custom&gt;");
  });

  it("returns an empty string for empty input", () => {
    expect(renderMarkdown("", true)).toBe("");
  });
});

/**
 * @vitest-environment jsdom
 */
describe("toMarkdown", () => {
  it("converts bold and italic HTML to Markdown", () => {
    expect(toMarkdown("<b>bold</b> and <i>italic</i>")).toBe(
      "**bold** and *italic*",
    );
  });

  it("converts paragraphs and line breaks", () => {
    expect(toMarkdown("<p>Hello</p><p>World</p>")).toBe("Hello\n\nWorld");
  });

  it("converts links", () => {
    expect(toMarkdown('<a href="https://example.com">Example</a>')).toBe(
      "[Example](https://example.com)",
    );
  });

  it("converts links with titles", () => {
    expect(
      toMarkdown('<a href="https://example.com" title="Site">Example</a>'),
    ).toBe('[Example](https://example.com "Site")');
  });

  it("converts images", () => {
    expect(toMarkdown('<img src="image.png" alt="A picture">')).toBe(
      "![A picture](image.png)",
    );
  });

  it("converts inline code", () => {
    expect(toMarkdown("<code>x &lt; 5</code>")).toBe("`x < 5`");
  });

  it("converts fenced code blocks", () => {
    expect(toMarkdown("<pre><code>const x = 1;</code></pre>")).toBe(
      "```\nconst x = 1;\n```",
    );
  });

  it("converts unordered lists", () => {
    expect(toMarkdown("<ul><li>One</li><li>Two</li></ul>")).toBe(
      "- One\n- Two",
    );
  });

  it("converts ordered lists", () => {
    expect(toMarkdown("<ol><li>One</li><li>Two</li></ol>")).toBe(
      "1. One\n2. Two",
    );
  });

  it("converts headings", () => {
    expect(toMarkdown("<h2>Title</h2>")).toBe("## Title");
  });

  it("converts blockquotes", () => {
    expect(toMarkdown("<blockquote>Hello\nWorld</blockquote>")).toBe(
      "> Hello\n> World",
    );
  });

  it("converts tables", () => {
    expect(
      toMarkdown(`
        <table>
          <tr><th>Name</th><th>Age</th></tr>
          <tr><td>Alice</td><td>20</td></tr>
        </table>
      `),
    ).toBe("| Name | Age |\n| --- | --- |\n| Alice | 20 |");
  });

  it("escapes pipes inside table cells", () => {
    expect(
      toMarkdown(`
        <table>
          <tr><th>A | B</th></tr>
        </table>
      `),
    ).toBe("| A \\| B |\n| --- |");
  });

  it("returns an empty string for empty input", () => {
    expect(toMarkdown("")).toBe("");
  });
});

it("escapes HTML inside inline code", () => {
  expect(renderMarkdown("`<b>hello</b>`", true)).toBe(
    "<code>&lt;b&gt;hello&lt;/b&gt;</code>",
  );
});

it("protects inline code from Markdown formatting", () => {
  expect(renderMarkdown("`**not bold**`", true)).toBe(
    "<code>**not bold**</code>",
  );
});

it("escapes HTML inside fenced code", () => {
  expect(renderMarkdown("```\n<div>hello</div>\n```", true)).toBe(
    "<pre><code>&lt;div&gt;hello&lt;/div&gt;\n</code></pre>",
  );
});

it("protects fenced code from Markdown formatting", () => {
  expect(renderMarkdown("```\n**not bold**\n```", true)).toBe(
    "<pre><code>**not bold**\n</code></pre>",
  );
});

it("protects math from Markdown formatting", () => {
  expect(renderMarkdown("$**x**$", true)).toBe("$**x**$");
});
it("escapes unmatched HTML tags", () => {
  expect(renderMarkdown("<custom>", true)).toBe("&lt;custom&gt;");
});
