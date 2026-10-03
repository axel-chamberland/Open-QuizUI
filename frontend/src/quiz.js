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
import {
  getSRSCounts,
  getSRSCurrentCategory,
  initSRS,
  nextSRSQuestion,
  prevSRSQuestion,
  updateSRS,
} from "./srs.js";
import { showAlert } from "./ui/alert.js";

const results = document.getElementById("results");

/**
 * Returns the actual index of the current question in quiz.questions.
 *
 * @returns {number}
 */
export function getCurrentQuestionArrayIndex() {
  return state.currentQuestionIndex;
}

/**
 * Moves to the next question.
 *
 * Normal mode uses state.questionOrder as the navigation order.
 * SRS mode uses the SRS priority queue to select the next question.
 *
 * @returns {Promise<void>}
 */
export async function nextQuestion() {
  if (state.srs) {
    const questionIndex = nextSRSQuestion(state.currentQuestionIndex);

    if (questionIndex === null) {
      renderResults();
      return;
    }

    goTo(questionIndex);
    return;
  }

  const currentOrderIndex = state.questionOrder.indexOf(
    state.currentQuestionIndex,
  );

  if (currentOrderIndex === -1) {
    return;
  }

  const questionIndex = state.questionOrder[currentOrderIndex + 1];

  if (questionIndex === undefined) {
    renderResults();
    return;
  }

  goTo(questionIndex);
}

/**
 * Moves to the previous question.
 *
 * Normal mode moves backward through state.questionOrder.
 * SRS mode undoes the most recent SRS answer.
 *
 * @returns {void}
 */
export function prevQuestion() {
  if (state.srs) {
    const questionIndex = prevSRSQuestion(state.quizStorageKey);

    if (questionIndex === null) {
      return;
    }

    results.style.display = "none";
    goTo(questionIndex);
    return;
  }

  const currentOrderIndex = state.questionOrder.indexOf(
    state.currentQuestionIndex,
  );

  if (currentOrderIndex <= 0) {
    return;
  }

  results.style.display = "none";

  const questionIndex = state.questionOrder[currentOrderIndex - 1];

  goTo(questionIndex);
}

/**
 * Displays a question by its actual index in quiz.questions.
 *
 * @param {number} questionIndex
 */
export function goTo(questionIndex) {
  if (questionIndex < 0) {
    questionIndex = 0;
  }

  state.currentQuestionIndex = questionIndex;

  if (questionIndex >= state.quiz.questions.length) {
    renderResults();
    return;
  }

  state.currentQuestion = state.quiz.questions[questionIndex];
  state.answerRevealed = false;

  if (!state.srs) {
    setStoredQuestionIndex(state.quizStorageKey, questionIndex);
  }

  updateQuestionNumbers();
  renderCurrentQuestion();
}

/**
 * Renders state.currentQuestion in the current display mode.
 *
 * @returns {void}
 */
function renderCurrentQuestion() {
  const question = state.currentQuestion;
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
    if (state.srs) {
      element.value = state.currentQuestionIndex + 1;
      return;
    }

    element.value = state.questionOrder.indexOf(state.currentQuestionIndex) + 1;
  });
}

export function updateQuestionCounts() {
  document.querySelectorAll(".question-count").forEach((element) => {
    element.textContent = state.questionOrder.length;
  });
}

/**
 * Handles a user's answer to a multiple-choice question.
 *
 * Updates the question result, records the answer, reveals the explanation,
 * and updates the SRS scheduler when SRS mode is active.
 *
 * @param {number} index - Index of the selected answer.
 * @param {HTMLButtonElement} button - Button corresponding to the selected answer.
 * @returns {Promise<void>}
 */
export async function handleAnswer(index, button) {
  saveStats();

  const questionArrayIndex = getCurrentQuestionArrayIndex();

  if (index === state.currentQuestion.correct_index) {
    revealAnswer();

    if (state.wrongAnswerCount === 0) {
      state.questionResults[questionArrayIndex] = CORRECT;
      state.questionAnswers[questionArrayIndex] = index;
      saveStats();
    }

    showMcqExplanation(state.currentQuestion);
  } else {
    button.classList.add("wrong");
    button.disabled = true;

    state.questionResults[questionArrayIndex] = WRONG;

    if (state.questionAnswers[questionArrayIndex] === null) {
      state.questionAnswers[questionArrayIndex] = index;
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

  const questionArrayIndex = getCurrentQuestionArrayIndex();

  state.optionButtons.forEach((btn) => (btn.disabled = true));

  if (state.questionResults[questionArrayIndex] === UNANSWERED) {
    state.questionResults[questionArrayIndex] = SKIPPED;
    saveStats();
  }

  document.body.classList.add("answer-revealed");

  if (document.getElementById("flashcard-box").style.display !== "none") {
    document.querySelector(".flashcard-answer").classList.add("visible");

    showFlashcardExplanation(state.currentQuestion);

    return;
  }

  const optionsContainer = document.getElementById("options");

  const buttons = optionsContainer.querySelectorAll("button");

  buttons[state.currentQuestion.correct_index].classList.add("correct");

  showMcqExplanation(state.currentQuestion);
}

export async function rateFSRS(rating) {
  if (!state.answerRevealed) {
    return;
  }

  const questionArrayIndex = getCurrentQuestionArrayIndex();

  const ratingNames = {
    1: "Again",
    2: "Hard",
    3: "Good",
    4: "Easy",
  };

  state.questionResults[questionArrayIndex] = rating === 1 ? WRONG : CORRECT;

  await updateSRS(ratingNames[rating], state.quizStorageKey);

  saveStats();
}

export function setQuizTitle(title) {
  const displayTitle = title.slice(0, 60);

  document.title = displayTitle;

  document.querySelectorAll(".title").forEach((e) => {
    e.textContent = title;
  });
}

export function renderQuestion(questionText, question) {
  document.body.classList.remove("answer-revealed");
  questionText.innerHTML = renderMarkdown(question.question, state.mathReady);

  if (state.srs) {
    updateSRSCounts();
  }
}

/** Update the due/reviewing/completed counts and underline the one corresponding
 to current question
 */
function updateSRSCounts() {
  const { due, reviewing, completed } = getSRSCounts();
  const currentCategory = getSRSCurrentCategory();

  document.querySelectorAll(".srs-due-count").forEach((element) => {
    element.textContent = String(due);
    element.classList.toggle("current", currentCategory === "due");
  });

  document.querySelectorAll(".srs-review-count").forEach((element) => {
    element.textContent = String(reviewing);
    element.classList.toggle("current", currentCategory === "reviewing");
  });

  document.querySelectorAll(".srs-completed-count").forEach((element) => {
    element.textContent = String(completed);
    element.classList.toggle("current", currentCategory === "completed");
  });
}

export function updateNavigation() {
  document.querySelectorAll(".prev-button").forEach((button) => {
    if (state.srs) {
      button.disabled = false;
      return;
    }

    button.disabled =
      state.questionOrder.indexOf(state.currentQuestionIndex) <= 0;
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

  state.mode = state.mode === "flashcard" ? "mcq" : "flashcard";

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

/**
 * Enables or disables spaced recognition system.
 *
 * When enabling SRS, initializes the SRS scheduler for the quiz.
 *
 * @returns {Promise<void>}
 */
export async function toggleSRS() {
  state.srs = !state.srs;

  // Change CSS class for state relative layout
  document.body.classList.toggle("srs-mode", state.srs);

  if (state.srs) {
    const initialized = await initSRS(
      state.quizStorageKey,
      state.currentQuestionIndex,
    );

    if (!initialized) {
      state.srs = false;
      document.body.classList.toggle("srs-mode", state.srs);
      showAlert(
        "Unable to load the FSRS library from the CDN. If it is not already cached, an internet connection is required. Please check your connection and try again.",
      );
      return;
    }

    updateSRSCounts();

    const questionIndex = nextSRSQuestion();

    if (questionIndex !== null) {
      goTo(questionIndex);
    }
  }
}
