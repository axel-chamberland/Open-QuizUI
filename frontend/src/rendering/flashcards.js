import { state } from "../state.js";
import { renderQuestion, updateNavigation } from "../quiz.js";
import { typesetMath } from "../shared/mathjax.js";
import { renderMarkdown } from "../shared/markdown.js";

export async function renderFlashcard() {
  const flashcardBox = document.getElementById("flashcard-box");
  const questionText = flashcardBox.querySelector(".flashcard-question");
  const answerEl = flashcardBox.querySelector(".flashcard-answer");

  if (!state.quiz.questions || state.quiz.questions.length === 0) {
    questionText.textContent = "No valid questions parsed";
    return;
  }

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

  flashcardBox.querySelector(".question-scroll").scrollTop = 0;

  await typesetMath();
}
