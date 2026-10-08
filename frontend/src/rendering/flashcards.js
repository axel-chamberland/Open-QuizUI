import { CORRECT, state, WRONG } from "../state.js";
import {
  nextQuestion,
  renderQuestion,
  updateNavigation,
  getCurrentQuestionArrayIndex,
} from "../quiz.js";
import { typesetMath } from "../shared/mathjax.js";
import { renderMarkdown } from "../shared/markdown.js";
import { saveStats } from "../persistence/stats.js";

export async function renderFlashcard() {
  const flashcardBox = document.getElementById("flashcard-box");
  const questionText = flashcardBox.querySelector(".flashcard-question");
  const answerEl = flashcardBox.querySelector(".flashcard-answer");
  const explanationEl = flashcardBox.querySelector(".flashcard-explanation");

  if (!state.quiz.questions || state.quiz.questions.length === 0) {
    questionText.textContent = "No valid questions parsed";
    return;
  }

  const questionArrayIndex = getCurrentQuestionArrayIndex();
  const question = state.quiz.questions[questionArrayIndex];
  state.currentQuestion = question;

  renderQuestion(questionText, question);

  const answerIndex =
    question.options.length === 1 ? 0 : question.correct_index;

  answerEl.innerHTML = renderMarkdown(
    question.options[answerIndex],
    state.mathReady,
  );

  explanationEl.innerHTML = question.explanation
    ? renderMarkdown(question.explanation, state.mathReady)
    : "";

  state.answerRevealed = false;

  updateNavigation();

  flashcardBox.querySelector("#flashcard-scroll").scrollTop = 0;

  await typesetMath();
}

export async function rateFlashcard(correct) {
  if (!state.answerRevealed) {
    return;
  }

  const questionArrayIndex = getCurrentQuestionArrayIndex();

  state.questionResults[questionArrayIndex] = correct ? CORRECT : WRONG;

  saveStats();
  nextQuestion();
}
