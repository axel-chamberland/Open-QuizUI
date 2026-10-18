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

| Question | Correct Answer | Explanation |
| --- | --- | --- |
| 1 | <Correct choice letter> | <Explanation.> |
| 2 | <Correct choice letter> | <Explanation.> |


```

Keep the questions, choices, and answer key in the same message. Most standard formats are supported. See [Troubleshoot](Troubleshooting.md#questions-or-answers-arent-being-detected-by-the-action-function) if the action function fails. If the Action fails to parse a particular format, consider opening an issue and providing the raw message.

Any text between an answer key item and the next answer key item (or the next question) is treated as that question's explanation.

### Flashcards

The Action also parses flashcards: questions that hold a single answer instead of choices. An explanation can follow each answer.

A Markdown table of questions, answers and explanations is read first, since a table is the clearest signal:

```text
| Question | Answer | Explanation |
| --- | --- | --- |
| <Question> | <Answer> | <Explanation.> |
```

The first usable table in the message is used, and a row without an answer is skipped.

A message without such a table is read from its question labels instead, with the answer below each question:

```text
# <Title>

## Question 1: <Question>

<Answer>

<Explanation.>
```

The answer may carry a label from the **Answer pattern** setting (`A:`, `Answer:`, `R:`, `Réponse:`). Without a label, the first paragraph below the question is the answer and the paragraphs after it are the explanation; questions without an answer are skipped.

The **Parse mode** setting decides which format is read. It defaults to `auto`: the message is read as a quiz with choices first, and as flashcards only when it holds no choices. Set it to **flashcards** to always show the message as flashcards — a quiz with choices then becomes cards, using the correct choice as the answer. Set it to **multiple-choice questions** to reject anything that is not a quiz with choices.

The **Flashcard format** setting decides which part of a flashcard message holds the cards. It defaults to `auto` (a table first, then question labels). Set it to **table** or **question labels** to read that part alone, without falling back to the other one.

The **Quiz mode** setting only decides which mode the quiz starts in; it can also be switched while taking the quiz.

## Taking a Quiz

Select an answer and move through the questions using the quiz controls. You can cycle through questions using the tap zones, **Enter**, **Space**, or the arrow keys. Choices can also be selected using the number keys.

Flashcards show their question alone. **Reveal answer** (the eye button), **Enter** or **Space** reveals the answer with its explanation, and the card is rated **✗** (unknown) or **✓** (known) once it is revealed, with the buttons or the **1** (unknown) and **2** (known) keys. Rating a card records it and moves on to the next one.

The quiz can be taken in either mode: the mode button, next to the timer, switches between multiple-choice questions and flashcards, whatever the quiz was created as.

Once the quiz is completed, cycling to the next page displays your results; see [Results](#results).

Quizzes can be edited at any time with the built-in editor; see [Editing a Quiz](#editing-a-quiz).

## Spaced Repetition

**Toggle Repetition**, in the **⋮** menu, switches the quiz to spaced repetition review (FSRS) and back, and remembers the choice for the next time the quiz is opened. The FSRS library is loaded from a CDN, so the first toggle needs an internet connection.

In repetition mode, the question number and the next button give way to the review queue:

- The first number counts the **due** cards: the questions that have not been reviewed yet.
- The second counts the **reviewing** cards: the ones seen before that are back in the queue.
- The third counts the **completed** cards: the ones whose next review is scheduled in the future, and are done with for now.

The count the question in view belongs to is underlined. The queue is filled with new cards, in the quiz's question order, up to the **Spaced repetition queue size**; from there the quiz moves from card to card in the order the reviews come due, which is why the question number is not shown. The next card appears after each rating, and the **◀** button undoes the last one.

Answers work as they do normally, and the card is then rated on a four-point scale instead — **Again**, **Hard**, **Good** or **Easy**, with the buttons or the **1** to **4** keys. The rating decides when the card comes back; **Again** counts as a wrong answer, and the other three as correct.

The **Spaced repetition queue size** and the FSRS parameters can be set per quiz, in the editor's **Additional Settings**:

- **Request retention**: the target chance of recalling a card when it is due; higher values review more often.
- **Maximum interval**: how far ahead a card can be scheduled, in days.
- **Enable fuzz**: spreads review dates randomly, so cards learned together do not all come back together.
- **Enable short-term scheduling**: lets new cards come back within the same session as well as later.

## Editing a Quiz

**Edit Question**, in the **⋮** menu of a question page, opens the editor on the question currently shown.

- **Title** renames the quiz.
- **Question** is the question text, with the same Markdown support as the rest of the quiz.
- **Answer Position** is the number of the correct choice.
- **Explanation** is shown after answering, when explanations are enabled.
- **Choices** holds one field per choice. A question's number of choices is set when it is created: one added while viewing a flashcard keeps its single choice, and one added while viewing a multiple-choice question is shaped like that question.

The **Save changes** button (a floppy-disk icon) saves the question, and **✕** closes the editor. **Reset Question** and **Reset Quiz**, in the editor's **⋮** menu, discard the local edits of the current question and of the whole quiz — resetting a question that was added removes it instead.

The edits are saved in your browser only, so they can be kept in two ways: **Copy Quiz** copies the quiz to your clipboard as text in the format the Action parses (paste it into a new message to reproduce the quiz), and **Download HTML** saves it as a standalone HTML Web App you can open and share outside Open WebUI.

> **Note:** iOS/iPadOS does not currently have a native way to view downloaded HTML Web Apps. Consider using something such as [HTML Preview](https://avinashs.com/html-preview), which you can install as a web app for offline use (tested on Safari, iPadOS 26).

### Question List

**Edit Questions**, under **Additional Settings**, opens the list of questions, where they are added, removed and reordered.

- Tapping a row selects it, and the editor then edits that question.
- Dragging a row moves the question up or down; **Save** applies the new order and **Cancel** leaves it as it was.
- **+ Add question** adds a blank question at the end, while **Add before** and **Add after** add one next to the current question.
- **Delete question** removes the current question without waiting for **Save**; a quiz always keeps at least one question.

Added questions are saved as soon as they are added, so **Cancel** offers to remove the questions added in the same session. A deletion is immediate.

## Results

Moving past the last question shows the results page (in repetition mode, it shows once the review queue is empty). It reports:

- **Score**: how many of the answered questions were correct. Unanswered questions are left out, so they do not count against the score.
- **Accuracy**: the share of the answered questions that were correct.
- **Correct**, **Wrong**, **Skipped** (the answer was revealed without answering) and **Unanswered** (never reached or revealed) counts, also drawn as a chart.
- **Time**, and the average time per question.

Under them, the correction sheet lists each question in order with your answer, the correct answer and the explanation — for a flashcard, your answer is the ✗ or ✓ it was given — colour-coded by how the question went.

**Restart Quiz** starts the quiz over after a confirmation, clearing the results.

The **◀** button goes back to the last question, from where the results page can be reached again.

## Limitations

- Questions and answers must be included in the same message when using the Action.
- Action-generated quizzes rely on recognizable formatting.
- Some Markdown structures may not be parsed as expected.
- Tool-generated quizzes depend on the model correctly following the required JSON format.
- Modified questions, your answers and the review schedule are saved in your browser's local storage, per quiz.
