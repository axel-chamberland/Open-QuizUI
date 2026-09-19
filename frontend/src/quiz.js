import { renderMCQ, showExplanation } from "./rendering/mcq.js";
import { saveStats } from "./persistence/stats.js";
import { renderResults } from "./rendering/results.js";
import { UNANSWERED, WRONG, CORRECT, SKIPPED, state } from "./state.js";
import { setStoredQuestionIndex } from "./persistence/progress.js";
import { renderMarkdown } from "./shared/markdown.js";
import { renderFlashcard } from "./rendering/flashcards.js";

const results = document.getElementById("results");

export function nextQuestion() {
  // If last question, go to results page
  if (
    state.currentQuestionIndex >= state.quiz.questions.length - 1 &&
    results.style.display === "none"
  ) {
    renderResults();
    return;
  }
  goTo(state.currentQuestionIndex + 1);
}

export function prevQuestion() {
  const results = document.getElementById("results");

  if (results.style.display !== "none") {
    results.style.display = "none";
    if (state.mode === "flashcard") {
      document.getElementById("flashcard-box").style.display = "";
      renderFlashcard();
      return;
    }

    document.getElementById("question-box").style.display = "";
    renderMCQ();
    return;
  }

  if (state.currentQuestionIndex <= 0) return;
  goTo(state.currentQuestionIndex - 1);
}

export function clampQuestionIndex(index, questionCount) {
  return Math.max(0, Math.min(index, questionCount - 1));
}

export function goTo(questionIndex) {
  // Clamp between first and last question
  questionIndex = clampQuestionIndex(
    questionIndex,
    state.quiz.questions.length,
  );

  state.currentQuestionIndex = questionIndex;

  setStoredQuestionIndex(state.quizStorageKey, state.currentQuestionIndex);

  state.answerRevealed = false;

  updateQuestionNumbers();
  if (state.mode === "flashcard") {
    document.querySelector(".flashcard-answer").classList.remove("visible");
    renderFlashcard();
    return;
  }
  renderMCQ();
}

export function updateQuestionNumbers() {
  document.querySelectorAll(".question-number").forEach((element) => {
    element.value = state.currentQuestionIndex + 1;
  });
}
export function handleAnswer(index, button) {
  saveStats();
  if (index === state.currentQuestion.correct_index) {
    button.classList.add("correct");
    button.disabled = true;
    state.answerRevealed = true;
    if (state.wrongAnswerCount === 0) {
      state.questionResults[state.currentQuestionIndex] = CORRECT;
      state.questionAnswers[state.currentQuestionIndex] = index;
      saveStats();
    }
    state.optionButtons.forEach((btn) => (btn.disabled = true));
    showExplanation(state.currentQuestion);
  } else {
    button.classList.add("wrong");
    button.disabled = true;
    state.questionResults[state.currentQuestionIndex] = WRONG;

    if (state.questionAnswers[state.currentQuestionIndex] === null) {
      state.questionAnswers[state.currentQuestionIndex] = index;
    }
    saveStats();
    state.wrongAnswerCount++;
    if (state.wrongAnswerCount === state.currentQuestion.options.length - 1) {
      revealAnswer();
    }
  }
}

export function revealAnswer() {
  state.answerRevealed = true;

  if (state.questionResults[state.currentQuestionIndex] === UNANSWERED) {
    state.questionResults[state.currentQuestionIndex] = SKIPPED;
    saveStats();
  }

  if (state.mode === "flashcard") {
    document.querySelector(".flashcard-answer").classList.add("visible");
    return;
  }

  state.currentQuestion = state.quiz.questions[state.currentQuestionIndex];

  const optionsContainer = document.getElementById("options");
  const buttons = optionsContainer.querySelectorAll("button");

  buttons[state.currentQuestion.correct_index].classList.add("correct");
  showExplanation(state.currentQuestion);
}

export function setQuizTitle(title) {
  const displayTitle = title.slice(0, 60);

  document.title = displayTitle;
  document.querySelectorAll(".title").forEach((e) => (e.textContent = title));
}

export function renderQuestion(questionText, question) {
  questionText.innerHTML = renderMarkdown(question.question, state.mathReady);
}

export function updateNavigation() {
  document.querySelectorAll(".prev-button").forEach((button) => {
    button.disabled = state.currentQuestionIndex === 0;
  });
}

export function updateQuestionCounts() {
  document.querySelectorAll(".question-count").forEach((element) => {
    element.textContent = state.quiz.questions.length;
  });
}

export function setMode(mode) {
  state.mode = mode;
  const quizPage = document.getElementById("question-box");
  const flashcardPage = document.getElementById("flashcard-box");

  const isFlashcard = mode === "flashcard";

  quizPage.style.display = isFlashcard ? "none" : "";
  flashcardPage.style.display = isFlashcard ? "" : "none";
}

export function toggleMode() {
  const questionBox = document.getElementById("question-box");
  const flashcardBox = document.getElementById("flashcard-box");

  // Toggle the mode
  state.mode = state.mode === "flashcard" ? "question" : "flashcard";

  // Show/hide the appropriate boxes
  if (state.mode === "flashcard") {
    flashcardBox.style.display = "";
    questionBox.style.display = "none";
  } else {
    questionBox.style.display = "";
    flashcardBox.style.display = "none";
  }
}

export function switchMode() {
  state.mode = state.mode === "mcq" ? "flashcard" : "mcq";
  setMode(state.mode);

  if (state.mode === "mcq") {
    renderMCQ();
  } else {
    renderFlashcard();
  }
}
