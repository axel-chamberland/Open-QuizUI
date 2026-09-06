# Open-QuizUI

Open-QuizUI is a tool / action function for displaying interactive multiple-choice quizzes inside Open WebUI using rich UI element embedding.

## Features

* Render MathJax for LaTeX expressions¹
* Full-screen / focus mode²
* Separate light/dark themes
* Save a quiz and share it as an HTML file
* Edit any question after quiz generation using the editor
* Results/stats page at the end with corrections
* Use one of many colour schemes or make your own
* Fits nicely on small screens

¹ MathJax must be enabled in the function's vavles (settings) for LaTeX expressions to render.

² On WebKit-based browsers on iOS/iPadOS, full-screen mode requires **"iframe Sandbox Allow Same Origin"** to be enabled in Open WebUI's interface settings.

## Example

<details open>
<summary>Dark Mode</summary>
<p align="center">
  <img src="examples/dark_mode.png" width="80%" />
</p>
</details>

<details>
<summary>Light Mode</summary>

<p align="center">
  <img src="examples/light_mode.png" width="80%" />
</p>

</details>

## Usage

There are two ways to use Open-QuizUI:

* **Tool:** Add the tool code through **Workspace → Tools → New Tool**.
* **Action Function:** Add the function code through **Admin Panel → Functions → New Function**.

Both options work, but the **action function is recommended for larger quizzes**. It allows the LLM to write quizzes naturally instead of having to follow a specific structure for tool calling.

The action function is triggered by pressing the action button below an LLM's message.

If the action function doesn't work with a particular format, it is often because the LLM made a formatting error. You can either fix the formatting manually or ask the LLM to use the tool in a follow-up message.

If you encounter a format that should be supported but isn't, please submit a bug report with the message content so it can be investigated. You can also try to fix the issue yourself and include any fixes or findings in the issue.

## Recommendations

* Any model will work. However, small models such as Qwen3.5 9B can fail heavy tool calls or break the action function by making formatting mistakes or doubting themselves outside a think block. Gemma usually has better formatting.
* Answer keys in Markdown tables are not fully supported yet. Most standard formatting should work, but you may need to adjust your prompt.
* For the recommended question and answer format for the action function, see the [Recommended Format](docs/Usage.md#recommended-format) documentation.
* The action function currently looks for French and English keywords such as `Question`, `Answer`, `A`, `Réponse`, and `R`, as well as numbered questions. If you use another language, you can modify the parser to add the appropriate keywords or adjust your prompt.
* The questions and answers must be in the **same message** for the action function to parse them. If the LLM provides them in separate messages, you can edit the first message and paste the answer key into it.

## Documentation

More detailed documentation is available in the [`docs/`](docs/) directory:

* [Getting Started](Getting-Started.md)
* [Usage](Usage.md)
* [Formatting](Formatting.md)
* [Customization](Customization.md)
* [Troubleshooting](Troubleshooting.md)
* [Development](Development.md)
* [Contributing](Contributing.md)
