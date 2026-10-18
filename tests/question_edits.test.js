/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, beforeEach } from "vitest";

import {
  appendQuestion,
  createQuestionTemplate,
  removeAppendedQuestion,
  initializeState,
  state,
} from "../frontend/src/state.js";
import { hashQuiz } from "../frontend/src/persistence/progress.js";
import {
  loadQuestionOrder,
  saveQuestionOrder,
} from "../frontend/src/persistence/question_order.js";
import {
  loadQuizEdits,
  removeLocalEditAndShift,
} from "../frontend/src/persistence/quiz_edits.js";
import {
  loadQuestionRemovals,
  saveQuestionRemovals,
} from "../frontend/src/persistence/question_removals.js";

const QUIZ = {
  title: "Test Quiz",
  questions: [
    { question: "Q1", options: ["a", "b"], correct_index: 0 },
    { question: "Q2", options: ["a", "b", "c", "d"], correct_index: 1 },
  ],
};

const QUIZ_KEY = hashQuiz(QUIZ);

function editsKey() {
  return `quizEdits_${QUIZ_KEY}`;
}

function storeEdits(edits) {
  localStorage.setItem(editsKey(), JSON.stringify(edits));
}

function storedEdits() {
  return JSON.parse(localStorage.getItem(editsKey()));
}

function removalsKey() {
  return `questionRemovals_${QUIZ_KEY}`;
}

describe("loadQuestionOrder", () => {
  beforeEach(() => localStorage.clear());

  it("falls back to the natural order", () => {
    expect(loadQuestionOrder(QUIZ_KEY, 3)).toEqual([0, 1, 2]);
  });

  it("keeps the stored order", () => {
    saveQuestionOrder(QUIZ_KEY, [2, 0, 1]);

    expect(loadQuestionOrder(QUIZ_KEY, 3)).toEqual([2, 0, 1]);
  });

  it("appends questions missing from the stored order", () => {
    // Two questions added after the order was saved.
    saveQuestionOrder(QUIZ_KEY, [1, 0]);

    expect(loadQuestionOrder(QUIZ_KEY, 4)).toEqual([1, 0, 2, 3]);
  });

  it("drops indexes that no longer exist", () => {
    saveQuestionOrder(QUIZ_KEY, [2, 1, 0]);

    expect(loadQuestionOrder(QUIZ_KEY, 2)).toEqual([1, 0]);
  });

  it("ignores duplicates", () => {
    saveQuestionOrder(QUIZ_KEY, [1, 1, 0]);

    expect(loadQuestionOrder(QUIZ_KEY, 2)).toEqual([1, 0]);
  });

  it("leaves out the questions deleted locally", () => {
    expect(loadQuestionOrder(QUIZ_KEY, 3, new Set([1]))).toEqual([0, 2]);
  });

  it("does not bring a deleted question back when normalizing", () => {
    // The order was saved before the question was deleted.
    saveQuestionOrder(QUIZ_KEY, [1, 0]);

    expect(loadQuestionOrder(QUIZ_KEY, 3, new Set([1]))).toEqual([0, 2]);
  });
});

describe("deleted questions", () => {
  beforeEach(() => {
    localStorage.clear();
    document.body.innerHTML = `<script id="app-data" type="application/json">${JSON.stringify(
      { quiz: QUIZ },
    )}</script>`;
  });

  it("round trips the deleted indexes", () => {
    saveQuestionRemovals(QUIZ_KEY, new Set([0, 2]));

    expect(loadQuestionRemovals(QUIZ_KEY)).toEqual(new Set([0, 2]));
  });

  it("stores nothing when nothing was deleted", () => {
    saveQuestionRemovals(QUIZ_KEY, new Set());

    expect(localStorage.getItem(removalsKey())).toBeNull();
  });

  it("keeps a deleted question out of the order on load", () => {
    saveQuestionRemovals(QUIZ_KEY, new Set([0]));

    initializeState(structuredClone(QUIZ));

    expect(state.questionOrder).toEqual([1]);
    expect(state.removedQuestions).toEqual(new Set([0]));
  });

  it("does not resurrect a deleted question on load", () => {
    saveQuestionRemovals(QUIZ_KEY, new Set([1]));
    saveQuestionOrder(QUIZ_KEY, [1, 0]);

    initializeState(structuredClone(QUIZ));

    expect(state.questionOrder).toEqual([0]);
  });

  it("moves off a deleted question the browser was left on", () => {
    saveQuestionRemovals(QUIZ_KEY, new Set([0]));
    localStorage.setItem(`currentQuestionIndex_${QUIZ_KEY}`, "0");

    initializeState(structuredClone(QUIZ));

    expect(state.currentQuestionIndex).toBe(1);
  });
});

describe("loadQuizEdits", () => {
  beforeEach(() => {
    localStorage.clear();
    document.body.innerHTML = `<script id="app-data" type="application/json">${JSON.stringify(
      { quiz: QUIZ },
    )}</script>`;
    initializeState(structuredClone(QUIZ));
  });

  it("applies edits to existing questions", () => {
    const edited = { question: "edited", options: ["a", "b"], correct_index: 1 };

    storeEdits({ 0: edited });

    loadQuizEdits(state);

    expect(state.quiz.questions[0]).toEqual(edited);
  });

  it("appends questions stored past the end of the quiz", () => {
    const addedA = { question: "added A", options: ["a", "b"], correct_index: 0 };
    const addedB = { question: "added B", options: ["a", "b"], correct_index: 1 };

    storeEdits({ 2: addedA, 3: addedB });

    loadQuizEdits(state);

    expect(state.quiz.questions).toHaveLength(4);
    expect(state.quiz.questions[2]).toEqual(addedA);
    expect(state.quiz.questions[3]).toEqual(addedB);
  });

  it("extends the order and the per-question state for appended questions", () => {
    storeEdits({ 2: { question: "added", options: ["a", "b"], correct_index: 0 } });

    loadQuizEdits(state);

    expect(state.questionOrder).toEqual([0, 1, 2]);
    expect(state.questionResults[2]).toBe(0);
    expect(state.questionAnswers[2]).toBeNull();
  });

  it("fills gaps so stored indexes stay aligned", () => {
    const added = { question: "added", options: ["a", "b"], correct_index: 0 };

    storeEdits({ 3: added });

    loadQuizEdits(state);

    expect(state.quiz.questions).toHaveLength(4);
    expect(state.quiz.questions[3]).toEqual(added);
  });

  it("loads the title alongside appended questions", () => {
    storeEdits({
      title: "Renamed Quiz",
      2: { question: "added", options: ["a", "b"], correct_index: 0 },
    });

    loadQuizEdits(state);

    expect(state.quiz.title).toBe("Renamed Quiz");
    expect(state.quiz.questions).toHaveLength(3);
  });
});

describe("createQuestionTemplate", () => {
  beforeEach(() => {
    localStorage.clear();
    initializeState(structuredClone(QUIZ));
  });

  it("matches the option count of the last question", () => {
    const template = createQuestionTemplate();

    expect(template.options).toHaveLength(4);
    expect(template.question).toBe("");
    expect(template.correct_index).toBe(0);
    expect(template.explanation).toBe("");
  });
});

describe("appendQuestion", () => {
  beforeEach(() => {
    localStorage.clear();
    initializeState(structuredClone(QUIZ));
  });

  it("appends at the end and extends the indexed state", () => {
    const index = appendQuestion(createQuestionTemplate());

    expect(index).toBe(2);
    expect(state.quiz.questions).toHaveLength(3);
    expect(state.questionOrder).toEqual([0, 1, 2]);
    expect(state.questionResults).toHaveLength(3);
    expect(state.questionAnswers).toHaveLength(3);
  });
});

describe("removeAppendedQuestion", () => {
  beforeEach(() => {
    localStorage.clear();
    initializeState(structuredClone(QUIZ));
  });

  it("removes the question and its slot in the order", () => {
    appendQuestion({ question: "added", options: ["a", "b"], correct_index: 0 });

    removeAppendedQuestion(2);

    expect(state.quiz.questions).toHaveLength(2);
    expect(state.questionOrder).toEqual([0, 1]);
    expect(state.questionResults).toHaveLength(2);
    expect(state.questionAnswers).toHaveLength(2);
  });

  it("shifts the questions after the removed one down an index", () => {
    appendQuestion({ question: "added A", options: ["a", "b"], correct_index: 0 });
    appendQuestion({ question: "added B", options: ["a", "b"], correct_index: 0 });

    removeAppendedQuestion(2);

    expect(state.quiz.questions[2].question).toBe("added B");
    expect(state.questionOrder).toEqual([0, 1, 2]);
  });
});

describe("added question round trip", () => {
  beforeEach(() => {
    localStorage.clear();
    document.body.innerHTML = `<script id="app-data" type="application/json">${JSON.stringify(
      { quiz: QUIZ },
    )}</script>`;
    initializeState(structuredClone(QUIZ));
  });

  it("survives a reload with the same index, order and slot", () => {
    // What the editor does when a question is added.
    const index = appendQuestion(createQuestionTemplate());

    state.quiz.questions[index].question = "added";
    localStorage.setItem(
      editsKey(),
      JSON.stringify({ [index]: state.quiz.questions[index] }),
    );
    saveQuestionOrder(QUIZ_KEY, state.questionOrder);

    // Reload.
    initializeState(structuredClone(QUIZ));
    loadQuizEdits(state);

    expect(state.quiz.questions).toHaveLength(3);
    expect(state.quiz.questions[2].question).toBe("added");
    expect(state.questionOrder).toEqual([0, 1, 2]);
    expect(state.questionResults).toHaveLength(3);
  });

  it("comes back in the stored order when it was reordered", () => {
    const index = appendQuestion(createQuestionTemplate());

    state.quiz.questions[index].question = "added";
    localStorage.setItem(
      editsKey(),
      JSON.stringify({ [index]: state.quiz.questions[index] }),
    );
    // The added question was dragged to the front and saved.
    saveQuestionOrder(QUIZ_KEY, [2, 0, 1]);

    initializeState(structuredClone(QUIZ));
    loadQuizEdits(state);

    expect(state.questionOrder).toEqual([2, 0, 1]);
  });

  it("is gone after being removed, without leaving an edit behind", () => {
    const index = appendQuestion(createQuestionTemplate());

    localStorage.setItem(
      editsKey(),
      JSON.stringify({ [index]: state.quiz.questions[index] }),
    );

    removeLocalEditAndShift(index);
    removeAppendedQuestion(index);

    initializeState(structuredClone(QUIZ));
    loadQuizEdits(state);

    expect(state.quiz.questions).toHaveLength(2);
    expect(state.questionOrder).toEqual([0, 1]);
  });
});

describe("removeLocalEditAndShift", () => {
  beforeEach(() => {
    localStorage.clear();
    initializeState(structuredClone(QUIZ));
  });

  it("drops the removed question's edit", () => {
    storeEdits({ 2: { question: "added" }, title: "Renamed" });

    removeLocalEditAndShift(2);

    expect(storedEdits()).toEqual({ title: "Renamed" });
  });

  it("shifts the edits of the questions after it", () => {
    storeEdits({
      0: { question: "edited" },
      2: { question: "removed" },
      3: { question: "after" },
    });

    removeLocalEditAndShift(2);

    expect(storedEdits()).toEqual({
      0: { question: "edited" },
      2: { question: "after" },
    });
  });

  it("removes the store when nothing is left", () => {
    storeEdits({ 2: { question: "removed" } });

    removeLocalEditAndShift(2);

    expect(localStorage.getItem(editsKey())).toBeNull();
  });
});
