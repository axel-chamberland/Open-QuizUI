# Usage

Open-QuizUI supports two ways of creating quizzes: the **Tool** and the **Action** function.

## Tool

The Tool generates quizzes using a structured JSON format that Open-QuizUI processes directly. **Function Calling** must be set to **Native** in the model settings.

## Action

The Action parses quiz content from the model's response.

### Recommended Format

```text
# <Title>

Question 1: <Question>

A. <Choice>
B. <Choice>
<Additional choices as necessary>

Question 2: <Question>

A. <Choice>
B. <Choice>
<Additional choices as necessary>

# Answer key

1. <Letter corresponding to the correct choice>
2. <Letter corresponding to the correct choice>
```

Keep the questions, choices, and answer key in the same message. Most standard formats are supported. If the Action fails to parse a particular format, consider opening an issue and providing the raw message.

Any text between an answer key item and the next answer key item (or the next question) is treated as that question's explanation:

## Taking a Quiz

Select an answer and move through the questions using the quiz controls. You can cycle through questions using the tap zones, **Enter**, **Space**, or the arrow keys. Choices can also be selected using the number keys.

Once the quiz is completed, cycling to the next page displays your statistics and corrections, along with an option to restart the quiz.

Quizzes can be edited, although edits are currently saved only in your browser. However, you can also download a quiz as an HTML Web App, allowing you to share it outside of Open WebUI.

> **Note:** iOS/iPadOS does not currently have a native way to view downloaded HTML Web Apps. Consider opening them using an app such as Dropbox or Microsoft Edge.

## Results

After finishing the quiz, Open-QuizUI shows your score and lets you review the results.

## Limitations

* Questions and answers must be included in the same message when using the Action.
* Action-generated quizzes rely on recognizable formatting.
* Some Markdown structures may not be parsed as expected.
* Tool-generated quizzes depend on the model correctly following the required JSON format.
* Modified questions are saved in your browser's local storage.
