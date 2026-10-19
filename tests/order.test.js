/**
 * @vitest-environment jsdom
 */
import { readFileSync } from "node:fs";
import { describe, it, beforeEach, expect, vi } from "vitest";

const indexHtml = readFileSync("frontend/index.html", "utf8");

/*
 * The overlay scrolls the row it just added, or the current question's
 * row, into view. jsdom has no layout and no scrollIntoView at all.
 */
Element.prototype.scrollIntoView = vi.fn();

// order.js has top-level event listeners, so the markup has to be in
// place before it is imported.
document.documentElement.innerHTML =
  indexHtml.match(/<html[^>]*>([\s\S]*)<\/html>/i)?.[1] ?? indexHtml;

const { openOrderEditor } = await import("../frontend/src/rendering/order.js");

const {
  closeEditorConfirm,
  openEditor,
} = await import("../frontend/src/rendering/editor.js");

const { state } = await import("../frontend/src/state.js");

const QUIZ = {
  title: "Test Quiz",
  questions: [
    { question: "Q1", options: ["A", "B"], correct_index: 0 },
    { question: "Q2", options: ["A", "B"], correct_index: 0 },
    { question: "Q3", options: ["A", "B"], correct_index: 0 },
  ],
};

function rows() {
  return Array.from(document.querySelectorAll("#order-editor-list .order-row"));
}

function rowIndexes() {
  return rows().map((row) => Number(row.dataset.questionIndex));
}

function editorNumber() {
  return document.getElementById("editor-question-number").textContent;
}

describe("question list overlay", () => {
  beforeEach(() => {
    localStorage.clear();

    document.getElementById("app-data").textContent = JSON.stringify({
      quiz: QUIZ,
    });

    state.quiz = structuredClone(QUIZ);
    state.quizStorageKey = "test-quiz";
    state.builtInQuestionCount = QUIZ.questions.length;
    state.removedQuestions = new Set();
    state.questionOrder = [0, 1, 2];
    state.questionResults = [];
    state.questionAnswers = [];
    state.mode = "mcq";
    state.srs = false;
    state.currentQuestionIndex = 1;
    state.srsQueueSize = 20;
    state.srsConfig = {
      request_retention: 0.9,
      maximum_interval: 365,
      enable_fuzz: true,
      enable_short_term: true,
    };

    // The list is opened from the editor, so the editor is open on a
    // question first.
    openEditor();
    openOrderEditor();
  });

  it("marks the question the editor is on", () => {
    const current = document.querySelector("#order-editor-list .order-current");

    expect(current.dataset.questionIndex).toBe("1");
    expect(document.querySelectorAll(".order-current")).toHaveLength(1);
  });

  it("adds a question at the end", () => {
    document.getElementById("order-editor-add").click();

    expect(rowIndexes()).toEqual([0, 1, 2, 3]);
    expect(state.questionOrder).toEqual([0, 1, 2, 3]);
  });

  it("adds a question before the current one", () => {
    document.getElementById("order-editor-add-before").click();

    expect(rowIndexes()).toEqual([0, 3, 1, 2]);
    expect(state.questionOrder).toEqual([0, 3, 1, 2]);
  });

  it("adds a question after the current one", () => {
    document.getElementById("order-editor-add-after").click();

    expect(rowIndexes()).toEqual([0, 1, 3, 2]);
    expect(state.questionOrder).toEqual([0, 1, 3, 2]);
  });

  it("leaves the editor where it is when a question is added", () => {
    document.getElementById("order-editor-add-after").click();

    expect(state.currentQuestionIndex).toBe(1);

    // Nothing is asked: the new row is there to be picked.
    expect(
      document.getElementById("global-prompt").classList.contains("visible"),
    ).toBe(false);

    expect(document.getElementById("order-editor").classList.contains("visible"))
      .toBe(true);
    expect(editorNumber()).toBe("Question 2 of 4");
  });

  it("deletes the current question and shows the next one", () => {
    document.getElementById("order-editor-delete").click();
    document.getElementById("global-prompt-yes").click();

    expect(rowIndexes()).toEqual([0, 2]);
    expect(state.removedQuestions.has(1)).toBe(true);
    expect(state.currentQuestionIndex).toBe(2);

    // The editor follows the question that took its place.
    expect(editorNumber()).toBe("Question 2 of 2");
  });

  it("falls back to the previous question when the last one is deleted", () => {
    state.currentQuestionIndex = 2;

    openOrderEditor();

    document.getElementById("order-editor-delete").click();
    document.getElementById("global-prompt-yes").click();

    expect(rowIndexes()).toEqual([0, 1]);
    expect(state.currentQuestionIndex).toBe(1);
  });

  it("keeps the quiz's last question", () => {
    state.questionOrder = [1];

    openOrderEditor();

    document.getElementById("order-editor-delete").click();

    expect(state.removedQuestions.size).toBe(0);
    expect(rowIndexes()).toEqual([1]);

    expect(document.getElementById("global-prompt-message").textContent).toBe(
      "A quiz needs at least one question.",
    );

    document.getElementById("global-prompt-yes").click();
  });

  it("removes the questions it added when it is cancelled", () => {
    document.getElementById("order-editor-add").click();

    document.getElementById("order-editor-cancel").click();
    document.getElementById("global-prompt-yes").click();

    expect(state.quiz.questions).toHaveLength(3);
    expect(state.questionOrder).toEqual([0, 1, 2]);

    expect(
      document.getElementById("order-editor").classList.contains("visible"),
    ).toBe(false);
  });

  it("sends the editor back to the last question when an added one goes", () => {
    document.getElementById("order-editor-add").click();

    // Pick the added question without leaving the list.
    rows()[3].click();

    expect(state.currentQuestionIndex).toBe(3);

    document.getElementById("order-editor-cancel").click();
    document.getElementById("global-prompt-yes").click();

    expect(state.currentQuestionIndex).toBe(2);
    expect(editorNumber()).toBe("Question 3 of 3");

    // The editor is showing the question it fell back to.
    expect(document.querySelector("#editor-question textarea").value).toBe(
      "Q3",
    );
  });

  it("closes the question list when the editor is closed", () => {
    closeEditorConfirm();
    document.getElementById("global-prompt-no").click();

    // Staying in the editor keeps the list up.
    expect(
      document.getElementById("order-editor").classList.contains("visible"),
    ).toBe(true);

    closeEditorConfirm();
    document.getElementById("global-prompt-yes").click();

    expect(
      document.getElementById("order-editor").classList.contains("visible"),
    ).toBe(false);
    expect(document.getElementById("editor").style.display).toBe("none");
  });

  it("does not move the editor's question number while the order is dragged", () => {
    expect(editorNumber()).toBe("Question 2 of 3");

    // Drag the first question past the last one.
    const list = rows();

    list[0].dispatchEvent(new Event("dragstart"));
    list[2].dispatchEvent(new Event("drop"));

    expect(rowIndexes()).toEqual([1, 2, 0]);
    expect(editorNumber()).toBe("Question 2 of 3");
  });

  it("moves the editor's question number when the order is saved", () => {
    const list = rows();

    list[0].dispatchEvent(new Event("dragstart"));
    list[2].dispatchEvent(new Event("drop"));

    document.getElementById("order-editor-save").click();

    expect(editorNumber()).toBe("Question 1 of 3");
  });

  it("picks the question a row is clicked on", () => {
    rows()[2].click();

    expect(state.currentQuestionIndex).toBe(2);
    expect(editorNumber()).toBe("Question 3 of 3");

    expect(
      document.querySelector(".order-current").dataset.questionIndex,
    ).toBe("2");

    // Nothing was waiting to be saved.
    expect(
      document.getElementById("global-prompt").classList.contains("visible"),
    ).toBe(false);
  });

  it("asks before leaving unsaved changes behind", () => {
    document.querySelector("#editor-question textarea").value = "edited";

    rows()[2].click();

    // The switch is offered, not made.
    expect(state.currentQuestionIndex).toBe(1);

    document.getElementById("global-prompt-no").click();

    expect(state.currentQuestionIndex).toBe(1);

    rows()[2].click();
    document.getElementById("global-prompt-yes").click();

    expect(state.currentQuestionIndex).toBe(2);
  });

  it("saves the staged order", () => {
    const list = rows();

    list[0].dispatchEvent(new Event("dragstart"));
    list[2].dispatchEvent(new Event("drop"));

    document.getElementById("order-editor-save").click();

    expect(state.questionOrder).toEqual([1, 2, 0]);
    expect(localStorage.getItem("questionOrder_test-quiz")).toBe(
      JSON.stringify([1, 2, 0]),
    );
  });
});
