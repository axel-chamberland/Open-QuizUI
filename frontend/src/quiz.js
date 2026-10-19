import { renderMCQ } from "./rendering/mcq.js";
import { saveStats } from "./persistence/stats.js";
import { renderResults } from "./rendering/results.js";
import {
  appendQuestion,
  createQuestionTemplate,
  removeAppendedQuestion,
  UNANSWERED,
  WRONG,
  CORRECT,
  SKIPPED,
  state,
} from "./state.js";
import { setStoredQuestionIndex } from "./persistence/progress.js";
import { saveAppDataOverrides } from "./persistence/app_data.js";
import {
  removeLocalEdit,
  removeLocalEditAndShift,
  saveLocalEdit,
} from "./persistence/quiz_edits.js";
import { saveQuestionOrder } from "./persistence/question_order.js";
import { saveQuestionRemovals } from "./persistence/question_removals.js";
import { renderMarkdown } from "./shared/markdown.js";
import { renderFlashcard } from "./rendering/flashcards.js";
import {
  canUndoSRS,
  getSRSCounts,
  getSRSCurrentCategory,
  initSRS,
  nextSRSQuestion,
  prevSRSQuestion,
  removeQuestionFromSRS,
  updateSRS,
} from "./srs.js";
import { showAlert } from "./ui/alert.js";
import {
  hideRatingIndicator,
  showRatingIndicator,
} from "./ui/rating_indicator.js";

/**
 * Hides the results page, for navigation that leaves it.
 *
 * Looked up on demand so the module stays usable without the quiz's
 * markup in place.
 *
 * @returns {void}
 */
function hideResults() {
  document.getElementById("results").style.display = "none";
}

/**
 * Whether the results page is the page in view.
 *
 * @returns {boolean}
 */
function isResultsVisible() {
  return document.getElementById("results").style.display !== "none";
}

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
    const questionIndex = nextSRSQuestion();

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
 * SRS mode undoes the most recent SRS answer, and with none to undo -
 * none rated since the page loaded, or none rated at all - steps back
 * from the results page to the question in view, as normal mode does.
 *
 * @returns {void}
 */
export function prevQuestion() {
  if (state.srs) {
    const questionIndex = prevSRSQuestion(state.quizStorageKey);

    if (questionIndex === null) {
      /*
       * There is no rating to undo when none was given since the page
       * loaded - the undo history is not persisted, so a reload leaves
       * it empty - and none when the queue was already empty. Stepping
       * back from the results page still shows the question they were
       * reached from, the way it does outside SRS mode.
       */
      if (!isResultsVisible()) {
        return;
      }

      const lastOrderIndex = state.questionOrder.length - 1;

      if (lastOrderIndex < 0) {
        return;
      }

      hideRatingIndicator();

      hideResults();

      // A number past the last question leaves no question in view,
      // which is the case the last question in the order is for.
      goTo(
        state.questionOrder.includes(state.currentQuestionIndex)
          ? state.currentQuestionIndex
          : state.questionOrder[lastOrderIndex],
      );

      return;
    }

    hideRatingIndicator();

    hideResults();
    goTo(questionIndex);
    return;
  }

  /*
   * The results page sits after the last question - the current index
   * is either the last question or, when the navigation field jumped
   * past the end, an index the quiz does not have. Either way,
   * stepping back from it shows that last question rather than the one
   * before it.
   */
  if (isResultsVisible()) {
    const lastOrderIndex = state.questionOrder.length - 1;

    if (lastOrderIndex < 0) {
      return;
    }

    hideResults();
    goTo(state.questionOrder[lastOrderIndex]);
    return;
  }

  const currentOrderIndex = state.questionOrder.indexOf(
    state.currentQuestionIndex,
  );

  if (currentOrderIndex <= 0) {
    return;
  }

  hideResults();

  goTo(state.questionOrder[currentOrderIndex - 1]);
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
  renderCurrentQuestionView();
}

/**
 * Displays a question by the number shown in the navigation field.
 *
 * The field counts positions in the navigation order, except in SRS
 * mode where it shows the question's own index (see
 * updateQuestionNumbers). Handing that number to goTo directly lands
 * on the wrong question as soon as the order differs from the quiz's
 * own order.
 *
 * A number past the last question goes to the results page, like
 * stepping forward off the end does.
 *
 * @param {number} position 1-based number from the navigation field.
 * @returns {void}
 */
export function goToPosition(position) {
  // A number below the first question means the first one.
  if (!Number.isFinite(position) || position < 1) {
    position = 1;
  }

  const questionIndex = state.srs
    ? position - 1
    : state.questionOrder[position - 1];

  if (questionIndex === undefined) {
    goTo(state.quiz.questions.length);
    return;
  }

  goTo(questionIndex);
}

/**
 * Renders state.currentQuestion in the current display mode.
 *
 * @returns {void}
 */
export function renderCurrentQuestionView() {
  const question = state.currentQuestion;

  let mode = state.mode;

  if (mode === "flashcard" || question.options.length < 2) {
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
 * Appends a blank question to the quiz and saves it.
 *
 * The question is persisted exactly like an edit made in the editor -
 * the whole question, under the next free index - so it survives a
 * refresh. Its slot in the navigation order is persisted with it, and
 * can be placed right before or after an existing question; a question
 * is only ever appended to the quiz itself, whatever its slot in the
 * order, so every stored index keeps pointing at the same question.
 *
 * @param {number|null} [orderPosition] Position in the navigation
 *   order to put the question at, or null to append it last.
 * @returns {number} Index of the added question.
 */
export function addQuestion(orderPosition = null) {
  const index = appendQuestion(createQuestionTemplate());

  if (orderPosition !== null) {
    // appendQuestion put it last; move it next to the current question.
    state.questionOrder.splice(state.questionOrder.indexOf(index), 1);
    state.questionOrder.splice(orderPosition, 0, index);
  }

  saveLocalEdit(index, false);
  saveQuestionOrder(state.quizStorageKey, state.questionOrder);

  updateQuestionNumbers();
  updateQuestionCounts();

  if (state.srs) {
    updateSRSCounts();
  }

  return index;
}

/**
 * Removes a question that was added in the editor.
 *
 * Everything indexed alongside the question follows it out: its stored
 * edit (with the edits behind it shifted down), the navigation order,
 * its result, its recorded answer, and the SRS scheduler state.
 *
 * @param {number} index Index of the added question.
 * @returns {void}
 */
export function removeAddedQuestion(index) {
  removeLocalEditAndShift(index);
  removeQuestionFromSRS(index);
  removeAppendedQuestion(index);

  saveQuestionOrder(state.quizStorageKey, state.questionOrder);

  updateQuestionNumbers();
  updateQuestionCounts();

  if (state.srs) {
    updateSRSCounts();
  }
}

/**
 * Deletes a question from the quiz.
 *
 * A question added in the editor is taken out of the quiz array, and
 * the indexes behind it move down (removeAddedQuestion). One of the
 * quiz's own questions cannot be: the quiz is the baseline that the
 * stored edits, results, order and SRS cards are keyed against, so the
 * index has to keep its meaning and the question is marked as deleted
 * instead. Either way it leaves the navigation order, which is what
 * makes it gone as far as the quiz is concerned.
 *
 * @param {number} index Question index to delete.
 * @returns {void}
 */
export function deleteQuestion(index) {
  if (index >= state.builtInQuestionCount) {
    removeAddedQuestion(index);
    return;
  }

  state.removedQuestions.add(index);

  // A stored edit for it has nothing left to apply to.
  removeLocalEdit(index);
  removeQuestionFromSRS(index, false);

  state.questionOrder = state.questionOrder.filter((item) => item !== index);

  saveQuestionRemovals(state.quizStorageKey, state.removedQuestions);
  saveQuestionOrder(state.quizStorageKey, state.questionOrder);

  updateQuestionNumbers();
  updateQuestionCounts();

  if (state.srs) {
    updateSRSCounts();
  }
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

  if (document.getElementById("question-box").style.display === "none") {
    return;
  }

  const optionsContainer = document.getElementById("options");

  const buttons = optionsContainer.querySelectorAll("button");

  buttons[state.currentQuestion.correct_index].classList.add("correct");
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
  showRatingIndicator(ratingNames[rating]);
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

/**
 * Update the due/reviewing/completed counts and underline the one
 * corresponding to the current question.
 */
export function updateSRSCounts() {
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
      /*
       * SRS mode steps back through this session's ratings, so the
       * button has nothing to do until one has been given.
       */
      button.disabled = !canUndoSRS(state.quizStorageKey);
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

export function switchMode() {
  state.mode = state.mode === "mcq" ? "flashcard" : "mcq";

  setMode(state.mode);
  saveAppDataOverrides(state.quizStorageKey, { mode: state.mode });

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
  if (!state.srs) {
    const initialized = await initSRS(
      state.quizStorageKey,
      state.currentQuestionIndex,
    );

    if (!initialized) {
      showAlert(
        "Unable to load the FSRS library from the CDN. If it is not already cached, an internet connection is required. Please check your connection and try again.",
      );
      return;
    }
  }

  // Toggle srs
  state.srs = !state.srs;

  // Persist the startup preference so the mode survives a refresh
  saveAppDataOverrides(state.quizStorageKey, { srsOnLoad: state.srs });

  /*
   * Regular navigation only persists the position while SRS is off.
   * When disabling SRS, persist the position the quiz stays on so a
   * refresh returns to the same question.
   */
  if (!state.srs) {
    setStoredQuestionIndex(state.quizStorageKey, state.currentQuestionIndex);
  }

  // Change CSS class for state relative layout
  document.body.classList.toggle("srs-mode", state.srs);

  /*
   * The field counts positions in the navigation order outside SRS
   * mode and the question's own index inside it, so it has to be
   * rewritten when the mode changes.
   */
  updateQuestionNumbers();

  /*
   * The back button steps through the question order outside SRS mode
   * and through this session's ratings inside it, and neither is
   * rewritten by the navigation below when the queue is empty.
   */
  updateNavigation();

  if (state.srs) {
    updateSRSCounts();

    const questionIndex = nextSRSQuestion();

    if (questionIndex !== null) {
      goTo(questionIndex);
    }
  }
}
