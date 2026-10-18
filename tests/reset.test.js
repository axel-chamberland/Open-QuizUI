/**
 * @vitest-environment jsdom
 */
import { readFileSync } from "node:fs";
import { describe, it, beforeEach, expect, vi } from "vitest";
import { state, UNANSWERED } from "../frontend/src/state.js";

const indexHtml = readFileSync("frontend/index.html", "utf8");

vi.mock("../frontend/src/persistence/quiz_edits.js", () => ({
  removeLocalEdit: vi.fn(),
  removeAllLocalEdits: vi.fn(),
  saveLocalEdit: vi.fn(),
}));

vi.mock("../frontend/src/rendering/mcq.js", () => ({
  renderMCQ: vi.fn(),
}));

// editor.js uses setQuizTitle, but we don't want the test to modify
// the real quiz title through its side effects.
vi.mock("../frontend/src/quiz.js", async () => {
  const actual = await vi.importActual("../frontend/src/quiz.js");

  return {
    ...actual,
    setQuizTitle: vi.fn(),
  };
});

// editor.js has a top-level event listener, so the required DOM must exist
// before importing it.
document.documentElement.innerHTML =
  indexHtml.match(/<html[^>]*>([\s\S]*)<\/html>/i)?.[1] ?? indexHtml;

const {
  closeEditorConfirm,
  hasUnsavedEditorChanges,
  openEditor,
  restoreQuestionToDefault,
  restoreQuizToDefault,
  saveEdit,
  updateEditorQuestionNumber,
} = await import("../frontend/src/rendering/editor.js");

const { restartQuiz } = await import("../frontend/src/rendering/results.js");

const { removeLocalEdit, removeAllLocalEdits } =
  await import("../frontend/src/persistence/quiz_edits.js");

const { setQuizTitle } = await import("../frontend/src/quiz.js");

const { renderMCQ } = await import("../frontend/src/rendering/mcq.js");

describe("restoreQuestionToDefault", () => {
  beforeEach(() => {
    const appData = document.getElementById("app-data");

    appData.textContent = JSON.stringify({
      quiz: {
        title: "Original quiz",
        questions: [
          {
            question: "Original question 1",
            options: ["A", "B"],
            correct_index: 0,
          },
          {
            question: "Original question 2",
            options: ["C", "D"],
            correct_index: 0,
          },
        ],
      },
    });

    state.currentQuestionIndex = 1;

    state.quiz = {
      title: "Edited quiz",
      questions: [
        {
          question: "Edited question 1",
          options: ["X", "Y"],
          correct_index: 1,
        },
        {
          question: "Edited question 2",
          options: ["Z", "W"],
          correct_index: 1,
        },
      ],
    };

    vi.clearAllMocks();
  });

  it("restores only the current question", () => {
    const originalQuestions = structuredClone(
      JSON.parse(document.getElementById("app-data").textContent).quiz
        .questions,
    );

    const otherQuestion = structuredClone(state.quiz.questions[0]);

    restoreQuestionToDefault();

    document.getElementById("global-prompt-yes").click();

    expect(state.quiz.questions[1]).toEqual(originalQuestions[1]);
    expect(state.quiz.questions[0]).toEqual(otherQuestion);
    expect(removeLocalEdit).toHaveBeenCalledWith(1);
  });
});

describe("restoreQuizToDefault", () => {
  beforeEach(() => {
    const appData = document.getElementById("app-data");

    appData.textContent = JSON.stringify({
      quiz: {
        title: "Original quiz",
        questions: [
          {
            question: "Original question",
            options: ["A", "B"],
            correct_index: 0,
          },
        ],
      },
    });

    state.currentQuestionIndex = 0;

    state.quiz = {
      title: "Edited quiz",
      questions: [
        {
          question: "Edited question",
          options: ["X", "Y"],
          correct_index: 1,
        },
      ],
    };

    state.quizStorageKey = "test-quiz";

    vi.clearAllMocks();
  });

  it("restores the entire quiz", () => {
    const originalQuiz = structuredClone(
      JSON.parse(document.getElementById("app-data").textContent).quiz,
    );

    restoreQuizToDefault();

    document.getElementById("global-prompt-yes").click();

    expect(state.quiz).toEqual(originalQuiz);
    expect(setQuizTitle).toHaveBeenCalledWith(originalQuiz.title);
    expect(removeAllLocalEdits).toHaveBeenCalled();
  });

  it("brings back the questions deleted locally", () => {
    localStorage.setItem("questionRemovals_test-quiz", JSON.stringify([0]));
    state.removedQuestions = new Set([0]);

    restoreQuizToDefault();

    document.getElementById("global-prompt-yes").click();

    expect(state.removedQuestions).toEqual(new Set());
    expect(localStorage.getItem("questionRemovals_test-quiz")).toBeNull();
    expect(state.questionOrder).toEqual([0]);
  });
});

describe("closeEditorConfirm", () => {
  beforeEach(() => {
    localStorage.clear();

    document.getElementById("editor").style.display = "";

    state.quiz = {
      title: "Test quiz",
      questions: [
        { question: "A", options: ["A", "B"], correct_index: 0 },
        { question: "B", options: ["A", "B"], correct_index: 0 },
        { question: "C", options: ["A", "B"], correct_index: 0 },
      ],
    };
    // The quiz's own order, with the third question moved to the front.
    state.questionOrder = [2, 0, 1];
    state.quizStorageKey = "test-quiz";
    state.mode = "mcq";
    state.srs = false;
    state.currentQuestionIndex = 2;
    // Stale: the editor moved on to the added question.
    state.currentQuestion = state.quiz.questions[0];

    vi.clearAllMocks();
  });

  function leaveEditor() {
    closeEditorConfirm();
    document.getElementById("global-prompt-yes").click();
  }

  it("leaves the quiz on the question the editor was showing", () => {
    leaveEditor();

    expect(state.currentQuestion).toBe(state.quiz.questions[2]);
    expect(document.querySelector(".question-number").value).toBe("1");
    expect(document.getElementById("editor").style.display).toBe("none");
  });

  it("persists the question it leaves on", () => {
    leaveEditor();

    expect(localStorage.getItem("currentQuestionIndex_test-quiz")).toBe("2");
  });

  it("does not move the stored position in SRS mode", () => {
    state.srs = true;

    leaveEditor();

    expect(state.currentQuestion).toBe(state.quiz.questions[2]);
    expect(localStorage.getItem("currentQuestionIndex_test-quiz")).toBe(null);
  });
});

describe("updateEditorQuestionNumber", () => {
  beforeEach(() => {
    state.quiz = {
      title: "Test quiz",
      questions: [
        { question: "A", options: ["A", "B"], correct_index: 0 },
        { question: "B", options: ["A", "B"], correct_index: 0 },
        { question: "C", options: ["A", "B"], correct_index: 0 },
      ],
    };
    // The quiz's own order, with the third question moved to the front.
    state.questionOrder = [2, 0, 1];
    state.currentQuestionIndex = 0;
  });

  function editorNumber() {
    return document.getElementById("editor-question-number").textContent;
  }

  it("shows the question's position in the saved order", () => {
    updateEditorQuestionNumber();

    expect(editorNumber()).toBe("Question 2 of 3");
  });

  it("counts the questions that are left", () => {
    // A question was deleted, so it is out of the order.
    state.questionOrder = [2, 0];

    updateEditorQuestionNumber();

    expect(editorNumber()).toBe("Question 2 of 2");
  });
});

describe("hasUnsavedEditorChanges", () => {
  beforeEach(() => {
    state.quiz = {
      title: "Test quiz",
      questions: [
        {
          question: "A",
          options: ["A", "B"],
          correct_index: 0,
          explanation: "",
        },
      ],
    };
    state.questionOrder = [0];
    state.currentQuestionIndex = 0;
    state.srsQueueSize = 20;
    state.srsConfig = {
      request_retention: 0.9,
      maximum_interval: 365,
      enable_fuzz: true,
      enable_short_term: true,
    };

    openEditor();
  });

  it("is false right after the editor opens", () => {
    expect(hasUnsavedEditorChanges()).toBe(false);
  });

  it("is true after a field was changed", () => {
    document.querySelector("#editor-question textarea").value = "changed";

    expect(hasUnsavedEditorChanges()).toBe(true);
  });

  it("is false again after saving", async () => {
    document.querySelector("#editor-question textarea").value = "changed";

    await saveEdit();

    expect(hasUnsavedEditorChanges()).toBe(false);
  });
});

describe("restartQuiz", () => {
  beforeEach(() => {
    /*
     * Off by default: an earlier SRS test in this file leaves the
     * flag on, and restarting with it on would drive the suite into
     * loading the FSRS library just to reset itself.
     */
    state.srs = false;

    state.quiz = {
      questions: [{}, {}, {}],
    };

    state.quizStorageKey = "test-quiz";
    state.currentQuestionIndex = 2;
    state.answerRevealed = true;
    state.wrongAnswerCount = 3;
    state.questionResults = ["correct", "wrong", "correct"];
    state.questionAnswers = [0, 1, 2];
    state.questionOrder = [0, 1, 2];

    state.timer = {
      interval: null,
      elapsed: 120,
      start: 123,
      visible: false,
    };

    document.getElementById("question-corrections").innerHTML =
      "<p>old correction</p>";

    document.getElementById("results").style.display = "";
    document.getElementById("question-box").style.display = "none";
    document.getElementById("restart-confirm").style.display = "flex";

    vi.clearAllMocks();
  });

  it("resets the quiz state and returns to the first question", async () => {
    await restartQuiz();

    expect(state.currentQuestionIndex).toBe(0);
    expect(state.answerRevealed).toBe(false);
    expect(state.wrongAnswerCount).toBe(0);

    expect(state.questionResults).toEqual([UNANSWERED, UNANSWERED, UNANSWERED]);

    expect(state.questionAnswers).toEqual([null, null, null]);

    expect(state.timer.elapsed).toBe(0);
    expect(state.timer.interval).toBe(null);
    expect(state.timer.start).toBe(null);

    expect(document.getElementById("question-corrections").innerHTML).toBe("");

    expect(document.getElementById("results").style.display).toBe("none");

    expect(document.getElementById("question-box").style.display).toBe("");

    expect(document.getElementById("restart-confirm").style.display).toBe(
      "none",
    );

    expect(renderMCQ).toHaveBeenCalled();
  });
});
