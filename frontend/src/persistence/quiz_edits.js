import { state } from "../state.js";

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
  } catch (e) {
    console.error("Failed to load quiz edits:", e);
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
