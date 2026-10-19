import { state } from "../state.js";
import { formatQuizAsFlashcards, formatQuizAsText } from "./formatting.js";

/**
 * Copies the question in view.
 *
 * @returns {Promise<void>}
 */
export async function copyQuestion() {
  const question = state.quiz.questions[state.currentQuestionIndex];

  await copyToClipboard(
    formatQuiz({ title: state.quiz.title, questions: [question] }),
  );
}

/**
 * Copies the quiz using state.questionOrder as the question order.
 *
 * @returns {Promise<void>}
 */
export async function copyQuiz() {
  await copyToClipboard(formatQuiz(orderedQuiz()));
}

/**
 * Copies the quiz as flashcards, a question per table row.
 *
 * A quiz that holds choices is written as cards too, each answered by
 * its correct choice.
 *
 * @returns {Promise<void>}
 */
export async function copyQuizAsFlashcards() {
  await copyToClipboard(formatQuizAsFlashcards(orderedQuiz()));
}

/**
 * The quiz, with its questions in the order the quiz shows them.
 *
 * @returns {{title: string, questions: Array}} Ordered quiz.
 */
function orderedQuiz() {
  return {
    ...state.quiz,
    questions: state.questionOrder.map(
      (questionIndex) => state.quiz.questions[questionIndex],
    ),
  };
}

/**
 * Formats a quiz the way the Action reads it back.
 *
 * A quiz of single choice questions is one the Action reads as
 * flashcards, so it is written as the flashcard table. Anything else is
 * written as questions with choices: a message that holds choices is
 * read as multiple-choice questions, and cannot hold flashcards as
 * well.
 *
 * @param {{title: string, questions: Array}} quiz
 * @returns {string} The quiz as text.
 */
function formatQuiz(quiz) {
  if (quiz.questions.every(isSingleChoice)) {
    return formatQuizAsFlashcards(quiz);
  }

  return formatQuizAsText({
    ...quiz,
    questions: normalizeSingleChoiceQuestions(quiz.questions),
  });
}

/**
 * Whether a question holds a single choice, which is what the app
 * renders as a flashcard.
 *
 * @param {{options: string[]}} question
 * @returns {boolean} Whether the question is a flashcard.
 */
function isSingleChoice(question) {
  return question.options.length === 1;
}

/**
 * Adds a second option to questions with only one choice so that the
 * text representation remains parseable.
 *
 * @param {Array<{ options: string[] }>} questions
 * @returns {Array<{ options: string[] }>}
 */
function normalizeSingleChoiceQuestions(questions) {
  return questions.map((question) =>
    isSingleChoice(question)
      ? {
          ...question,
          options: [...question.options, "N/A"],
        }
      : question,
  );
}

async function copyToClipboard(text) {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (error) {
      console.warn("Clipboard API failed, trying fallback:", error);
    }
  }

  return copyToClipboardFallback(text);
}

function copyToClipboardFallback(text) {
  const textarea = document.createElement("textarea");

  textarea.value = text;
  textarea.style.position = "fixed";
  textarea.style.left = "-9999px";
  textarea.style.top = "0";
  textarea.setAttribute("readonly", "");

  document.body.appendChild(textarea);

  textarea.select();
  textarea.setSelectionRange(0, textarea.value.length);

  let success = false;

  try {
    success = document.execCommand("copy");
  } catch (error) {
    console.error("Fallback copy failed:", error);
  }

  document.body.removeChild(textarea);

  return success;
}
