import { appendQuestion, createQuestionTemplate, state } from "../state.js";

function getQuizEditsKey(quizStorageKey) {
  return `quizEdits_${quizStorageKey}`;
}

export function saveLocalEdit(index, titleChanged) {
  const key = getQuizEditsKey(state.quizStorageKey);

  let edits = {};

  try {
    edits = JSON.parse(localStorage.getItem(key)) || {};
  } catch {
    edits = {};
  }

  const questionChanged = hasQuestionChanged(index);
  const actualTitleChanged = titleChanged && hasTitleChanged();

  if (!questionChanged && !actualTitleChanged) {
    return false;
  }

  if (actualTitleChanged) {
    edits.title = state.quiz.title;
  }

  if (questionChanged) {
    edits[index] = state.quiz.questions[index];
  }

  try {
    localStorage.setItem(key, JSON.stringify(edits));
    return true;
  } catch (e) {
    console.error("Failed to save edit:", e);
    return false;
  }
}

function hasQuestionChanged(index) {
  const appData = JSON.parse(document.getElementById("app-data").textContent);

  return (
    JSON.stringify(state.quiz.questions[index]) !==
    JSON.stringify(appData.quiz.questions[index])
  );
}

function hasTitleChanged() {
  const appData = JSON.parse(document.getElementById("app-data").textContent);

  return state.quiz.title !== appData.quiz.title;
}

export function loadQuizEdits(state) {
  const key = getQuizEditsKey(state.quizStorageKey);

  try {
    const edits = JSON.parse(localStorage.getItem(key));

    if (!edits) {
      return;
    }

    if (edits.title !== undefined) {
      state.quiz.title = edits.title;
    }

    // Load edited questions
    for (const [index, question] of Object.entries(edits)) {
      const i = Number(index);
      if (Number.isInteger(i) && i >= 0 && i < state.quiz.questions.length) {
        state.quiz.questions[i] = question;
      }
    }

    appendStoredQuestions(edits);
  } catch (e) {
    console.error("Failed to load quiz edits:", e);
  }
}

/**
 * Appends the questions stored past the end of the quiz.
 *
 * A question the user adds in the editor is saved like any other edit,
 * at the index right after the last question, so it comes back here on
 * the next load with the same index. Gaps (which a normal session
 * cannot produce) are filled with blank questions so the stored
 * indexes stay aligned.
 *
 * @param {object} edits Stored edits, keyed by question index.
 * @returns {void}
 */
function appendStoredQuestions(edits) {
  const pending = Object.entries(edits)
    .map(([index, question]) => [Number(index), question])
    .filter(([index]) => Number.isInteger(index) && index >= 0)
    .sort(([a], [b]) => a - b);

  for (const [index, question] of pending) {
    if (index < state.quiz.questions.length) {
      continue;
    }

    while (state.quiz.questions.length < index) {
      appendQuestion(createQuestionTemplate());
    }

    appendQuestion(question);
  }
}

export function removeLocalEdit(index) {
  const key = getQuizEditsKey(state.quizStorageKey);

  let edits;

  try {
    edits = JSON.parse(localStorage.getItem(key)) || {};
  } catch {
    return false;
  }

  delete edits[index];

  // If nothing remains, remove the whole edits entry.
  if (Object.keys(edits).length === 0) {
    localStorage.removeItem(key);
  } else {
    localStorage.setItem(key, JSON.stringify(edits));
  }

  return true;
}

export function removeAllLocalEdits() {
  const key = getQuizEditsKey(state.quizStorageKey);
  localStorage.removeItem(key);
}

/**
 * Removes a question's local edit and shifts the edits of the
 * questions after it down by one.
 *
 * Used when an appended question is removed: the questions behind it
 * move down an index, and their stored edits have to follow, or they
 * would be loaded onto the wrong questions.
 *
 * @param {number} index Removed question index.
 * @returns {boolean} Whether the stored edits were updated.
 */
export function removeLocalEditAndShift(index) {
  const key = getQuizEditsKey(state.quizStorageKey);

  let edits;

  try {
    edits = JSON.parse(localStorage.getItem(key)) || {};
  } catch {
    return false;
  }

  const shifted = {};

  for (const [storedIndex, value] of Object.entries(edits)) {
    // The title lives in the same store, under a non-numeric key.
    if (storedIndex === "title") {
      shifted.title = value;
      continue;
    }

    const i = Number(storedIndex);

    if (!Number.isInteger(i) || i === index) {
      continue;
    }

    shifted[i > index ? i - 1 : i] = value;
  }

  try {
    if (Object.keys(shifted).length === 0) {
      localStorage.removeItem(key);
    } else {
      localStorage.setItem(key, JSON.stringify(shifted));
    }
  } catch (e) {
    console.error("Failed to update edits:", e);
    return false;
  }

  return true;
}
