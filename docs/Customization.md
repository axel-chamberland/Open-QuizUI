# Customization

## Fullscreen / Focus Mode

Open-QuizUI includes a fullscreen/focus mode that hides the surrounding Open WebUI interface and gives the quiz more space.

> **Note:** On iOS/iPadOS, fullscreen requires **"iframe Sandbox Allow Same Origin"** to be enabled in Open WebUI's interface settings when using WebKit. iOS and iPadOS WebKit do not support the standard fullscreen API for content embedded in an iframe, so this setting is required for Open-QuizUI's fullscreen mode to work. **If you must keep it off**, consider sideloading a Chromium or Gecko-based browser such as [Reynard Browser](https://github.com/minh-ton/reynard-browser).


## Themes

Open-QuizUI supports light and dark themes.


### Colour Scheme

The colour scheme can be customized at the top of the Tool/Action function's code. Each theme is defined using CSS variables.

For example:

```python
    "default_light": """
--bg: oklch(100% 0 0);
--btn: oklch(94% 0 0);
--text: oklch(20% 0 0);
--border: oklch(85% 0 0);

--success: #0fff93;
--danger: #ff4545;
--skipped: #ffb800;
--unanswered: #8a8a8a;

--correct_bg: color-mix(in srgb, var(--success) 30%, var(--btn));
--wrong_bg: color-mix(in srgb, var(--danger) 30%, var(--btn));
""",
    "default_dark": """
--bg: oklch(20% 0 0);
--btn: oklch(24% 0 0);
--text: oklch(94% 0 0);
--border: oklch(85% 0 0);

--success: #00ff00;
--danger: #ff0000;
--skipped: #ffcc00;
--unanswered: #999999;

--correct_bg: color-mix(in srgb, var(--success) 30%, var(--btn));
--wrong_bg: color-mix(in srgb, var(--danger) 30%, var(--btn));
"""

```

The main variables are:

* `--bg` — background colour
* `--btn` — button background
* `--text` — text colour
* `--border` — border colour
* `--success` — correct-answer colour
* `--danger` — incorrect-answer colour
* `--skipped` — skipped-question colour
* `--unanswered` — unanswered-question colour
* `--correct_bg` — button background for correct answers
* `--wrong_bg` — button background for incorrect answers

You can use any valid CSS colour value, including hexadecimal, RGB, HSL, and `oklch()`.

## Other Settings

Additional settings can be found in the function configuration.
