import { renderMCQ, showMcqExplanation } from "./rendering/mcq.js";
import { saveStats } from "./persistence/stats.js";
import { renderResults } from "./rendering/results.js";
import { UNANSWERED, WRONG, CORRECT, SKIPPED, state } from "./state.js";
import { setStoredQuestionIndex } from "./persistence/progress.js";
import { renderMarkdown } from "./shared/markdown.js";
import {
  renderFlashcard,
  showFlashcardExplanation,
} from "./rendering/flashcards.js";

const results = document.getElementById("results");

export function nextQuestion() {
  goTo(state.currentQuestionIndex + 1);
}

export function prevQuestion() {
  if (state.currentQuestionIndex <= 0) return;

  const results = document.getElementById("results");
  results.style.display = "none";
  goTo(state.currentQuestionIndex - 1);
}

export function goTo(questionIndex) {
  const questionCount = state.quiz.questions.length;

  if (questionIndex < 0) {
    questionIndex = 0;
  }

  // Results page
  if (questionIndex >= questionCount) {
    state.currentQuestionIndex = questionCount;
    setStoredQuestionIndex(state.quizStorageKey, state.currentQuestionIndex);

    renderResults();
    return;
  }

  state.currentQuestionIndex = questionIndex;
  setStoredQuestionIndex(state.quizStorageKey, state.currentQuestionIndex);

  state.answerRevealed = false;

  updateQuestionNumbers();

  const question = state.quiz.questions[questionIndex];
  const distractorCount = question.options.length - 1;

  let mode = state.mode;

  if (mode === "flashcard" || distractorCount < 2) {
    mode = "flashcard";
  }

  const quizPage = document.getElementById("question-box");
  const flashcardPage = document.getElementById("flashcard-box");

  if (mode === "flashcard") {
    quizPage.style.display = "none";
    flashcardPage.style.display = "";

    renderFlashcard();
    return;
  }

  quizPage.style.display = "";
  flashcardPage.style.display = "none";

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
    showMcqExplanation(state.currentQuestion);
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
  if (document.getElementById("flashcard-box").style.display !== "none") {
    document.querySelector(".flashcard-answer").classList.add("visible");
    showFlashcardExplanation(state.currentQuestion);

    document.getElementById("flashcard-rating").style.display = "flex";
    return;
  }

  state.currentQuestion = state.quiz.questions[state.currentQuestionIndex];

  const optionsContainer = document.getElementById("options");
  const buttons = optionsContainer.querySelectorAll("button");

  buttons[state.currentQuestion.correct_index].classList.add("correct");
  showMcqExplanation(state.currentQuestion);
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
  state.mode = state.mode === "flashcard" ? "mcq" : "flashcard";

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
