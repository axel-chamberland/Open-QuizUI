import { state } from "../state.js";
import { setSRSConfig, initSRS } from "../srs.js";
import {
  removeAllLocalEdits,
  removeLocalEdit,
  saveLocalEdit,
} from "../persistence/quiz_edits.js";
import { saveAppDataOverrides } from "../persistence/app_data.js";
import {
  loadQuestionOrder,
  clearQuestionOrder,
} from "../persistence/question_order.js";
import { clearQuestionRemovals } from "../persistence/question_removals.js";
import {
  goTo,
  removeAddedQuestion,
  setQuizTitle,
  updateSRSCounts,
} from "../quiz.js";
import { closeOrderEditor, openOrderEditor } from "./order.js";
import { showAlert, showPrompt } from "../ui/alert.js";

document
  .getElementById("editor-answer-number")
  .addEventListener("input", (e) => {
    e.target.value = e.target.value.replace(/\D/g, "");
  });

/**
 * Updates the "Question X of Y" line above the title field.
 *
 * The position is the question's place in the saved navigation order,
 * and the total is the number of questions that are left, so the line
 * is only rewritten when an order is actually saved - a drag that has
 * not been saved yet does not move it.
 *
 * @returns {void}
 */
export function updateEditorQuestionNumber() {
  const orderIndex = state.questionOrder.indexOf(state.currentQuestionIndex);
  const questionPosition =
    orderIndex === -1 ? state.currentQuestionIndex + 1 : orderIndex + 1;

  document.getElementById("editor-question-number").textContent =
    `Question ${questionPosition} of ${state.questionOrder.length}`;
}

export function openEditor() {
  const editor = document.getElementById("editor");

  // Hide current page
  document.getElementById("flashcard-box").style.display = "none";
  document.getElementById("question-box").style.display = "none";

  // Show editor page
  editor.style.display = "";

  const titleField = document.getElementById("editor-title");
  const questionField = document.getElementById("editor-question");
  const explanationField = document.getElementById("editor-explanation");
  const editorAnswer = document.getElementById("editor-answer-number");
  const optionsContainer = document.getElementById("editor-distractors");

  const question = state.quiz.questions[state.currentQuestionIndex];

  updateEditorQuestionNumber();

  // Set initial values
  titleField.innerHTML = `<textarea></textarea>`;
  titleField.querySelector("textarea").value = state.quiz.title;

  questionField.innerHTML = `<textarea></textarea>`;
  questionField.querySelector("textarea").value = question.question;

  explanationField.innerHTML = `<textarea></textarea>`;
  explanationField.querySelector("textarea").value = question.explanation || "";

  editorAnswer.value = question.correct_index + 1;

  optionsContainer.innerHTML = "";

  question.options.forEach((option) => {
    optionsContainer.appendChild(addEditorOption(option));
  });

  loadAdditionalSettings();

  rememberEditorValues();
}

/**
 * Controller for the additional settings fields.
 *
 * Keeps a snapshot of the values the editor was opened with, so
 * unchanged settings are not persisted as app data overrides.
 */
let additionalSettingsSnapshot = null;

/**
 * Reads the additional settings fields as state values.
 *
 * @returns {object} The FSRS config and SRS queue size from the fields.
 */
function getEditorSettingsValues() {
  const edit = (id) => document.getElementById(id);

  return {
    srsQueueSize: parseInt(edit("editor-srs-queue-size").value, 10),
    srsConfig: {
      request_retention: parseFloat(
        edit("editor-fsrs-request-retention").value,
      ),
      maximum_interval: parseInt(
        edit("editor-fsrs-maximum-interval").value,
        10,
      ),
      enable_fuzz: edit("editor-fsrs-enable-fuzz").checked,
      enable_short_term: edit("editor-fsrs-enable-short-term").checked,
    },
  };
}

/**
 * Fills the additional settings fields with the current FSRS values.
 *
 * @returns {void}
 */
function loadAdditionalSettings() {
  const config = state.srsConfig;

  document.getElementById("editor-srs-queue-size").value = state.srsQueueSize;
  document.getElementById("editor-fsrs-request-retention").value =
    config.request_retention;
  document.getElementById("editor-fsrs-maximum-interval").value =
    config.maximum_interval;
  document.getElementById("editor-fsrs-enable-fuzz").checked =
    config.enable_fuzz;
  document.getElementById("editor-fsrs-enable-short-term").checked =
    config.enable_short_term;

  additionalSettingsSnapshot = JSON.stringify(getEditorSettingsValues());
}

/**
 * Snapshot of the editor's fields, taken when the editor is opened or
 * saved, to tell later whether anything in it was changed.
 */
let editorSnapshot = null;

/**
 * Reads the question fields of the editor as values.
 *
 * @returns {object} Title, question, answer position, options and
 *   explanation, as they currently read.
 */
function getEditorQuestionValues() {
  const field = (id) => document.querySelector(`#${id} textarea`)?.value ?? "";

  const optionsContainer = document.getElementById("editor-distractors");

  return {
    title: field("editor-title"),
    question: field("editor-question"),
    explanation: field("editor-explanation"),
    answer: document.getElementById("editor-answer-number").value,
    options: Array.from(optionsContainer.querySelectorAll("textarea")).map(
      (textarea) => textarea.value,
    ),
  };
}

/**
 * Remembers the editor's fields as the saved state.
 *
 * @returns {void}
 */
function rememberEditorValues() {
  editorSnapshot = JSON.stringify([
    getEditorQuestionValues(),
    getEditorSettingsValues(),
  ]);
}

/**
 * Whether the editor holds changes that have not been saved.
 *
 * The question list asks before switching the editor to another
 * question, which would drop whatever is in these fields.
 *
 * @returns {boolean} Whether there is anything unsaved.
 */
export function hasUnsavedEditorChanges() {
  if (editorSnapshot === null) {
    return false;
  }

  return (
    JSON.stringify([getEditorQuestionValues(), getEditorSettingsValues()]) !==
    editorSnapshot
  );
}

document
  .getElementById("order-editor-open-button")
  .addEventListener("click", openOrderEditor);

/**
 * Validates the additional settings fields.
 *
 * @returns {boolean} Whether all additional settings are valid.
 */
function validateAdditionalSettings() {
  const retentionInput = document.getElementById(
    "editor-fsrs-request-retention",
  );
  const intervalInput = document.getElementById("editor-fsrs-maximum-interval");
  const queueInput = document.getElementById("editor-srs-queue-size");

  const retention = parseFloat(retentionInput.value);
  const maximumInterval = parseInt(intervalInput.value, 10);
  const queueSize = parseInt(queueInput.value, 10);

  let valid = true;

  const check = (input, condition) => {
    input.classList.remove("input-error");

    if (!condition) {
      input.classList.add("input-error");
      valid = false;
    }
  };

  check(
    retentionInput,
    !Number.isNaN(retention) && retention > 0 && retention < 1,
  );
  check(
    intervalInput,
    Number.isInteger(maximumInterval) && maximumInterval >= 1,
  );
  check(queueInput, Number.isInteger(queueSize) && queueSize >= 1);

  if (!valid) {
    showAlert(
      "Invalid Additional Settings: request retention must be between 0 and 1, and the other values must be positive integers.",
    );
  }

  return valid;
}

function addEditorOption(value) {
  const article = document.createElement("article");

  const textarea = document.createElement("textarea");
  textarea.value = value;

  const insertBtn = document.createElement("button");
  insertBtn.textContent = "+";
  insertBtn.onclick = () => {
    article.after(addEditorOption(""));
  };

  const deleteBtn = document.createElement("button");
  deleteBtn.textContent = "⌦";

  const promptDiv = document.createElement("div");
  promptDiv.className = "delete-prompt";

  const confirmBtn = document.createElement("button");
  confirmBtn.textContent = "Confirm";
  confirmBtn.onclick = () => article.remove();

  const cancelBtn = document.createElement("button");
  cancelBtn.textContent = "Cancel";
  cancelBtn.onclick = () => {
    promptDiv.style.display = "none";
  };

  deleteBtn.onclick = () => {
    promptDiv.style.display = "flex";
  };

  promptDiv.appendChild(confirmBtn);
  promptDiv.appendChild(cancelBtn);

  article.appendChild(insertBtn);
  article.appendChild(deleteBtn);
  article.appendChild(promptDiv);
  article.appendChild(textarea);

  return article;
}

// Returns false if the selected answer index does not exist in the DOM anymore
function validateAnswerIndex() {
  const answerInput = document.querySelector("#editor-answer-number");

  const val = parseInt(answerInput.value) - 1;

  const optionsContainer = document.getElementById("editor-distractors");
  const options = optionsContainer.querySelectorAll("article");

  if (val < 0 || val >= options.length) {
    answerInput.classList.add("input-error");
    showAlert("Invalid Index: The selected option no longer exists.");
    return false;
  }

  return true;
}

export function closeEditorConfirm() {
  showPrompt(
    "Exit? Unsaved changes will be lost.",
    closeEditor,
    null,
    "yes",
    "no",
  );
}

export async function saveEdit() {
  if (!validateAnswerIndex() || !validateAdditionalSettings()) {
    return;
  }

  // Extract data from DOM
  const newTitleText = document.querySelector("#editor-title textarea").value;
  const newQuestionText = document.querySelector(
    "#editor-question textarea",
  ).value;
  const newIndex =
    parseInt(document.querySelector("#editor-answer-number").value) - 1;
  const optionsContainer = document.getElementById("editor-distractors");
  const updatedOptions = Array.from(
    optionsContainer.querySelectorAll("textarea"),
  ).map((ta) => ta.value);

  const newExplanationText = document.querySelector(
    "#editor-explanation textarea",
  ).value;

  // Track whether the title was changed
  const titleChanged = state.quiz.title !== newTitleText;
  state.quiz.title = newTitleText;

  setQuizTitle(state.quiz.title);

  // Update global state
  state.quiz.questions[state.currentQuestionIndex].question = newQuestionText;
  state.quiz.questions[state.currentQuestionIndex].correct_index = newIndex;
  state.quiz.questions[state.currentQuestionIndex].options = updatedOptions;
  state.quiz.questions[state.currentQuestionIndex].explanation =
    newExplanationText;

  // Apply additional (FSRS) settings
  const settingsChanged = applyAdditionalSettings();

  // Persist the actual changes (locally)
  const questionSaved = saveLocalEdit(state.currentQuestionIndex, titleChanged);

  if (questionSaved || settingsChanged) {
    showAlert("Changes saved.");
  }

  // What is in the fields is the saved state now.
  rememberEditorValues();

  /*
   * A changed queue size only reaches the SRS queue when it is filled,
   * which happens at initialization. Re-run the initialization so the
   * new size applies right away; with SRS off there is no queue and the
   * next initialization picks the size up.
   */
  if (settingsChanged && state.srs) {
    await initSRS(state.quizStorageKey, state.currentQuestionIndex);

    updateSRSCounts();
  }
}

/**
 * Applies the additional settings fields to the runtime state and
 * persists them as app data overrides so they survive a refresh.
 *
 * Unchanged fields (matching what the editor was opened with) are not
 * persisted.
 *
 * @returns {boolean} Whether any setting differs from what the editor
 *   was opened with.
 */
function applyAdditionalSettings() {
  const values = getEditorSettingsValues();

  const settingsChanged =
    JSON.stringify(values) !== additionalSettingsSnapshot;

  setSRSConfig(values.srsConfig);

  state.srsQueueSize = values.srsQueueSize;

  if (settingsChanged) {
    saveAppDataOverrides(state.quizStorageKey, {
      srsConfig: { ...state.srsConfig },
      srsQueueSize: state.srsQueueSize,
    });
  }

  return settingsChanged;
}

function closeEditor() {
  const editor = document.getElementById("editor");

  editor.style.display = "none";

  // Reset UI state
  const options = document.getElementById("editor-distractors");
  options.innerHTML = "";

  /*
   * Anything the editor opened goes with it: the question list is not
   * modal (it has no backdrop), so the editor can be closed from
   * behind it.
   */
  closeOrderEditor();

  /*
   * Leave the quiz on the question the editor was showing - it can
   * have moved there, e.g. to a question added in the order editor -
   * so the question, the navigation field and the stored position all
   * agree again, in both navigation modes.
   */
  goTo(state.currentQuestionIndex);
}

export function restoreQuizToDefault() {
  showPrompt(
    "Restore the quiz to its original state?\nAll local edits will be discarded.",
    () => {
      // Update using app-data from last download
      const appData = JSON.parse(
        document.getElementById("app-data").textContent,
      );

      state.quiz = structuredClone(appData.quiz);
      setQuizTitle(state.quiz.title);

      // Reset the question order to the natural sequence, and bring
      // back the questions deleted locally.
      clearQuestionOrder(state.quizStorageKey);
      clearQuestionRemovals(state.quizStorageKey);
      state.removedQuestions = new Set();
      state.questionOrder = loadQuestionOrder(
        state.quizStorageKey,
        state.quiz.questions.length,
      );

      // Remove local storage edits
      removeAllLocalEdits();

      openEditor();
      showAlert("Quiz restored to default.");
    },
    null,
    "Yes",
    "No",
  );
}

export function restoreQuestionToDefault() {
  const appData = JSON.parse(document.getElementById("app-data").textContent);

  const index = state.currentQuestionIndex;

  /*
   * A question added in the editor has no original to restore: it only
   * exists locally, so resetting it means removing it again.
   */
  if (index >= appData.quiz.questions.length) {
    showPrompt(
      "Remove this added question?\nIt will be deleted from the quiz.",
      () => {
        removeAddedQuestion(index);

        state.currentQuestionIndex = Math.min(
          index,
          state.quiz.questions.length - 1,
        );

        openEditor();
        showAlert("Added question removed.");
      },
      null,
      "Yes",
      "No",
    );

    return;
  }

  showPrompt(
    "Restore the current question to its original state?\nAll local edits will be discarded.",
    () => {
      state.quiz.questions[index] = structuredClone(
        appData.quiz.questions[index],
      );

      removeLocalEdit(index);

      openEditor();
      showAlert("Question restored to default.");
    },
    null,
    "Yes",
    "No",
  );
}
