import { toMarkdown } from "./markdown.js";

export function formatTime(seconds) {
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;

  return `${String(minutes).padStart(2, "0")}:${String(remainingSeconds).padStart(2, "0")}`;
}

export function formatQuestionAsText(question, index) {
  const lines = [];

  const questionText = toMarkdown(question.question);

  lines.push(`Question ${index + 1}: ${questionText}`);
  lines.push("");

  for (const [i, option] of question.options.entries()) {
    const letter = String.fromCharCode(65 + i);

    lines.push(`${letter}. ${toMarkdown(option)}`);
  }

  return lines.join("\n");
}

/**
 * Escapes text for a table cell: a pipe would end the cell and a line
 * break would end the row.
 *
 * @param {string} text Cell text.
 * @returns {string} The text, fit for a cell.
 */
function escapeTableCell(text) {
  return String(text ?? "")
    .replace(/\|/g, "\\|")
    .replace(/\n/g, " ");
}

export function formatAnswerKey(questions) {
  const lines = [
    "Answer Key:",
    "",
    "| Question | Correct Answer | Explanation |",
    "| --- | --- | --- |",
  ];

  for (const [index, question] of questions.entries()) {
    const correctLetter = String.fromCharCode(65 + question.correct_index);

    const explanation = toMarkdown(question.explanation || "");

    lines.push(
      `| ${index + 1} | ${correctLetter} | ${escapeTableCell(explanation)} |`,
    );
  }

  return lines.join("\n");
}

export function formatQuizAsText(quiz) {
  const lines = [toMarkdown(quiz.title), ""];

  for (const [index, question] of quiz.questions.entries()) {
    lines.push(formatQuestionAsText(question, index));
    lines.push("");
  }

  lines.push(formatAnswerKey(quiz.questions));

  return lines.join("\n").trim();
}

/**
 * Formats a quiz as the flashcard table the Action reads: the questions
 * in the first column, their answers in the second and the explanations
 * in the third.
 *
 * A question with choices is answered by its correct choice, which is
 * how the Action reads one as a flashcard too.
 *
 * @param {{title: string, questions: Array}} quiz
 * @returns {string} The quiz as a table.
 */
export function formatQuizAsFlashcards(quiz) {
  const lines = [
    toMarkdown(quiz.title),
    "",
    "| Question | Answer | Explanation |",
    "| --- | --- | --- |",
  ];

  for (const question of quiz.questions) {
    // A single choice question is a card, so its only choice is the
    // answer whatever the recorded answer position says.
    const answerIndex =
      question.options.length === 1 ? 0 : question.correct_index;

    const questionText = escapeTableCell(toMarkdown(question.question));
    const answer = escapeTableCell(
      toMarkdown(question.options[answerIndex] ?? ""),
    );
    const explanation = escapeTableCell(toMarkdown(question.explanation || ""));

    lines.push(`| ${questionText} | ${answer} | ${explanation} |`);
  }

  return lines.join("\n").trim();
}
