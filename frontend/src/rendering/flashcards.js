import { CORRECT, state, WRONG } from "../state.js";
import { nextQuestion, renderQuestion, updateNavigation } from "../quiz.js";
import { typesetMath } from "../shared/mathjax.js";
import { renderMarkdown } from "../shared/markdown.js";
import { saveStats } from "../persistence/stats.js";

export async function renderFlashcard() {
  const flashcardBox = document.getElementById("flashcard-box");
  const questionText = flashcardBox.querySelector(".flashcard-question");
  const answerEl = flashcardBox.querySelector(".flashcard-answer");
  const explanationEl = flashcardBox.querySelector(".flashcard-explanation");
  const ratingEl = flashcardBox.querySelector("#flashcard-rating");

  if (!state.quiz.questions || state.quiz.questions.length === 0) {
    questionText.textContent = "No valid questions parsed";
    return;
  }

  answerEl.classList.remove("visible");
  explanationEl.style.display = "none";
  ratingEl.style.display = "none";

  const question = state.quiz.questions[state.currentQuestionIndex];
  state.currentQuestion = question;

  renderQuestion(questionText, question);

  const answerIndex =
    question.options.length === 1 ? 0 : question.correct_index;

  answerEl.innerHTML = renderMarkdown(
    question.options[answerIndex],
    state.mathReady,
  );

  state.answerRevealed = false;

  updateNavigation();

  flashcardBox.querySelector("#flashcard-scroll").scrollTop = 0;

  await typesetMath();
}

export function showFlashcardExplanation(question) {
  const explanationEl = document.querySelector(".flashcard-explanation");

  if (question.explanation) {
    explanationEl.innerHTML = renderMarkdown(
      question.explanation,
      state.mathReady,
    );
    explanationEl.style.display = "block";

    if (state.mathReady) {
      window.MathJax.typesetPromise([explanationEl]).catch((err) =>
        console.error("MathJax typesetting failed:", err),
      );
    }
  } else {
    explanationEl.innerHTML = "";
    explanationEl.style.display = "none";
  }
}

export function rateFlashcard(correct) {
  if (!state.answerRevealed) {
    return;
  }

  state.questionResults[state.currentQuestionIndex] = correct ? CORRECT : WRONG;

  saveStats();
  nextQuestion();
}
