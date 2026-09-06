# Formatting

Open-QuizUI supports **HTML formatting within quiz questions and answer choices**. Any valid HTML can be used to format their content.

When using the **Action** function, Markdown formatting is also supported and is converted to HTML when the Action is called.

**MathJax** is supported separately for rendering mathematical expressions.

## HTML

HTML can be used directly within questions and answer choices. This includes standard elements such as:

* **Text formatting** (`<strong>`, `<em>`, `<u>`, etc.)
* **Links** (`<a>`)
* **Images** (`<img>`)
* **Videos** (`<video>`)
* **Iframes** (`<iframe>`)
* **Lists** (`<ul>`, `<ol>`, `<li>`)
* **Code** (`<code>`, `<pre>`)
* **Tables** (`<table>`, `<tr>`, `<td>`, etc.)

Any valid HTML can be used as part of a question or answer choice.


> **Note:** Files uploaded to Open WebUI can be embedded using the `/api/files/<file_id>/content` endpoint. For example, an uploaded image can be referenced with `<img src="/api/files/<file_id>/content">`. However, these URLs will stop working if the quiz is downloaded and opened outside of Open WebUI. Keep this in mind when embedding your own files. Images can also be encoded as Base64 and stored directly inside the quiz, allowing them to work when the quiz is used outside of Open WebUI.


## Mathematics

LaTeX expressions can be rendered using MathJax (optional setting).

Inline math:

```text
$E = mc^2$
```

Displayed math:

```text
$$
E = mc^2
$$
```

## Code

Code can be included using HTML:

```html
<pre><code>print("Hello, world!")</code></pre>
```

## Tables

HTML tables can be used directly within questions and answer choices.

When using the Action function, Markdown tables are currently not converted to HTML.