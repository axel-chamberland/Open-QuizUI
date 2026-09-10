# Troubleshooting

## Quiz isn't showing up

If the quiz isn't appearing, check the following:

1. **Check your Open WebUI version.** Open-QuizUI requires **Open WebUI 0.10 or newer**.
2. **Check whether the model actually made the tool call.** Some smaller or less capable models may fail to call Open-QuizUI even when the request should produce a quiz. Try a larger or more capable model, or use the Action Function instead.
3. **Check the browser console** (`F12` → **Console**) for errors related to Open-QuizUI, tool calls, or the function/action.
4. **Reload Open WebUI** and try again.
5. If the issue persists, [open an issue](https://github.com/axel-chamberland/Open-QuizUI) with your Open WebUI version, model, relevant console errors, and any other details that may help reproduce the problem.

## Questions or answers aren't being detected by the Action Function

* Check that the questions and answer choices follow the supported formatting.
* The parser relies on specific **keywords, structure, and formatting** to identify questions and answer choices.
* Models can sometimes make small syntax errors in those keywords that prevent a question from being detected. Consider editing the message manually.
* A small formatting difference may prevent a question from being recognized.
* If the formatting appears correct but the question still isn't detected, consider [opening an issue](https://github.com/axel-chamberland/Open-QuizUI) with the message that caused the problem.
* If the format isn't currently supported, the example can help add support for that formatting in a future update.

## Math isn't rendering

If mathematical expressions are showing as plain text or not appearing correctly:

1. **Check that MathJax is enabled** in the function/action settings.
2. **Check the LaTeX syntax.** Make sure the expression uses valid LaTeX and the correct delimiters (for example, `$...$` for inline math or `$$...$$` for display math).
3. **Check your network connection.** Open-QuizUI loads MathJax from a CDN, so MathJax may fail to load if the CDN is blocked by your Wi-Fi, firewall, DNS filter, or browser extensions.
4. **Reload the page** after enabling MathJax or changing any network settings.
5. If it still doesn't work, **open your browser's developer console** (`F12` → **Console**) and check for errors mentioning `MathJax`, the CDN, or blocked network requests.

If MathJax works on other websites but not in Open-QuizUI, make sure MathJax is enabled and try disabling browser extensions that may block external scripts.
## Fullscreen isn't working

Make sure **"iframe Sandbox Allow Same Origin"** is enabled in Open WebUI's interface settings.

## Theme isn't working

* Check that the **theme name is spelled and set correctly**.
* After changing the theme, **call the tool/action again**. Changes to the configuration won't affect a quiz that has already been generated.
* If it still isn't working, check the theme configuration for syntax errors or missing variables.

## Something else is broken

Check the browser console for errors and open an issue on the [GitHub repository](https://github.com/axel-chamberland/Open-QuizUI) with the relevant details.
