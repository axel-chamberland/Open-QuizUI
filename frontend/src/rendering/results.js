import { setStoredQuestionIndex } from "../persistence/progress.js";
import { resetQuestionSRSState } from "../persistence/question_order.js";
import { updateQuestionNumbers } from "../quiz.js";
import { formatTime } from "../shared/formatting.js";
import { renderMarkdown } from "../shared/markdown.js";
import { typesetMath } from "../shared/mathjax.js";
import { initSRS } from "../srs.js";
import { UNANSWERED, WRONG, CORRECT, SKIPPED, state } from "../state.js";
import { saveTimer, updateTimer } from "../timer.js";
import { renderFlashcard } from "./flashcards.js";
import { renderMCQ } from "./mcq.js";

export async function renderResults() {
  const results = document.getElementById("results");

  // Hide current page
  const flashcardBox = document.getElementById("flashcard-box");
  flashcardBox.style.display = "none";
  const questionBox = document.getElementById("question-box");
  questionBox.style.display = "none";

  results.style.display = "";

  /*
   * Count only the questions that are still in the quiz: the results
   * of a question deleted in the editor are left behind with it.
   */
  const ordered = state.questionOrder.map(
    (index) => state.questionResults[index],
  );

  const correct = ordered.filter((x) => x === CORRECT).length;
  const wrong = ordered.filter((x) => x === WRONG).length;
  const unanswered = ordered.filter((x) => x === UNANSWERED).length;
  const skipped = ordered.filter((x) => x === SKIPPED).length;

  const total = state.questionOrder.length;
  const answered = correct + wrong;

  const accuracy = answered > 0 ? (correct / answered) * 100 : 0;

  const elapsed = state.timer.visible
    ? state.timer.elapsed + Math.floor((Date.now() - state.timer.start) / 1000)
    : Math.floor((Date.now() - state.defaultStartDate) / 1000);

  /*
   * The outcome row, in the order it is read: the bar and the key
   * under it carry the four counts, so they replace the tiles those
   * counts used to have.
   */
  const outcomes = [
    { className: "outcome-correct", label: "Correct", count: correct },
    { className: "outcome-wrong", label: "Wrong", count: wrong },
    { className: "outcome-skipped", label: "Skipped", count: skipped },
    { className: "outcome-unanswered", label: "Unanswered", count: unanswered },
  ];

  document.getElementById("score").textContent =
    `Score: ${correct}/${wrong + correct}`;

  document.getElementById("accuracy").textContent =
    `Accuracy: ${accuracy.toFixed(1)}%`;

  document.getElementById("time").textContent = `Time: ${formatTime(elapsed)}`;

  document.getElementById("averageTime").textContent =
    `Average time per question: ${formatTime(Math.floor(elapsed / total))}`;

  renderOutcomeBar(document.getElementById("stats-chart"), outcomes);
  showCorrectionSheet();

  await typesetMath();
}

/**
 * Renders the outcome bar and its key.
 *
 * An outcome no question ended in gets no segment, and a dimmed key
 * entry: the segment would be invisible either way, while the key
 * keeps saying the outcome exists and is empty.
 *
 * @param {HTMLElement} container Where the bar and the key go.
 * @param {Array<{className: string, label: string, count: number}>} outcomes
 *   The outcomes, in reading order.
 */
function renderOutcomeBar(container, outcomes) {
  const total = outcomes.reduce((sum, outcome) => sum + outcome.count, 0);

  if (total <= 0) {
    container.innerHTML = "";
    return;
  }

  const segments = outcomes
    .filter((outcome) => outcome.count > 0)
    .map(
      ({ className, count }) =>
        `<div class="${className}" style="flex: ${count}"></div>`,
    )
    .join("");

  const key = outcomes
    .map(
      ({ className, label, count }) => `
        <li class="${className}${count > 0 ? "" : " empty"}">
          <span class="swatch"></span>${label} <b>${count}</b>
        </li>`,
    )
    .join("");

  container.innerHTML = `
    <div class="stats-bar" aria-hidden="true">${segments}</div>
    <ul class="stats-bar-key">${key}</ul>
  `;
}

/**
 * Reads the "Your answer" line of a correction.
 *
 * A flashcard is rated rather than picked, so it shows the checkmark
 * convention. A multiple-choice question shows the option that was
 * picked, and one answered by rating it - spaced repetition review,
 * where the rating is the verdict - shows the same checkmarks instead
 * of reading as unanswered.
 *
 * @param {number} index Index of the question in state.quiz.questions.
 * @param {object} question The question at that index.
 * @returns {string} What the correction shows as the user's answer.
 */
function describeUserAnswer(index, question) {
  const result = state.questionResults[index];

  if (state.mode === "flashcard") {
    return result === CORRECT ? "✓" : result === WRONG ? "✗" : "Unanswered";
  }

  if (result === SKIPPED) {
    return "Skipped";
  }

  const userIndex = state.questionAnswers[index];

  if (userIndex !== null) {
    return question.options[userIndex];
  }

  return result === CORRECT ? "✓" : result === WRONG ? "✗" : "Unanswered";
}

function showCorrectionSheet() {
  const container = document.getElementById("question-corrections");
  const questions = state.quiz.questions;

  container.innerHTML = "";

  const resultClass = {
    [CORRECT]: "correct",
    [WRONG]: "wrong",
    [UNANSWERED]: "unanswered",
    [SKIPPED]: "skipped",
  };

  for (
    let orderIndex = 0;
    orderIndex < state.questionOrder.length;
    orderIndex++
  ) {
    const index = state.questionOrder[orderIndex];
    const question = questions[index];

    const correctAnswer = question.options[question.correct_index];

    const userAnswer = describeUserAnswer(index, question);

    const article = document.createElement("article");

    const currentClass = resultClass[state.questionResults[index]];

    article.innerHTML = `
<h3 class="${currentClass}">Question ${orderIndex + 1}</h3>

<p>${renderMarkdown(question.question, state.mathReady)}</p>

<p>
    <strong>Your answer:</strong>
    ${renderMarkdown(userAnswer, state.mathReady)}
</p>

<p>
    <strong>Correct answer:</strong>
    ${renderMarkdown(correctAnswer, state.mathReady)}
</p>

${
  question.explanation
    ? `
<p>
    <strong>Explanation:</strong>
    ${renderMarkdown(question.explanation, state.mathReady)}
</p>
`
    : ""
}
`;

    container.appendChild(article);
  }
}

export async function restartQuiz() {
  // Reset question state
  state.currentQuestionIndex = state.questionOrder[0];
  updateQuestionNumbers();
  state.answerRevealed = false;
  state.wrongAnswerCount = 0;

  // Reset stats
  state.questionResults = new Array(state.quiz.questions.length).fill(
    UNANSWERED,
  );
  state.questionAnswers = new Array(state.quiz.questions.length).fill(null);
  document.getElementById("question-corrections").innerHTML = "";

  // Reset timer
  clearInterval(state.timer.interval);
  state.timer.interval = null;

  state.timer.elapsed = 0;
  state.timer.start = state.timer.visible ? Date.now() : null;
  state.defaultStartDate = Date.now();

  const timerElements = document.querySelectorAll(".timer");

  if (state.timer.visible) {
    updateTimer();
    state.timer.interval = setInterval(updateTimer, 1000);
  } else {
    timerElements.forEach((timerElement) => {
      timerElement.textContent = formatTime(0);
    });
  }
  saveTimer();

  // Reset stored question
  setStoredQuestionIndex(state.quizStorageKey, state.currentQuestionIndex);

  // Reset SRS
  resetQuestionSRSState(state.quizStorageKey);
  if (state.srs) {
    await initSRS(state.quizStorageKey, state.currentQuestionIndex);
  }

  // Return to quiz
  const results = document.getElementById("results");

  results.style.display = "none";

  document.getElementById("restart-confirm").style.display = "none";

  if (state.mode === "flashcard") {
    const flashcardBox = document.getElementById("flashcard-box");
    flashcardBox.style.display = "";
    renderFlashcard();
    return;
  }

  const questionBox = document.getElementById("question-box");
  questionBox.style.display = "";
  document.getElementById("restart-confirm").style.display = "none";

  renderMCQ();
}

export function confirmRestart() {
  document.getElementById("restart-confirm").style.display = "flex";
}

export function cancelRestart() {
  document.getElementById("restart-confirm").style.display = "none";
}
