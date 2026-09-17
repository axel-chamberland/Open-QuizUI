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
  renderQuiz: vi.fn(),
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

const { restoreQuestionToDefault, restoreQuizToDefault } =
  await import("../frontend/src/rendering/editor.js");

const { restartQuiz } = await import("../frontend/src/rendering/results.js");

const { removeLocalEdit, removeAllLocalEdits } =
  await import("../frontend/src/persistence/quiz_edits.js");

const { setQuizTitle } = await import("../frontend/src/quiz.js");

const { renderQuiz } = await import("../frontend/src/rendering/mcq.js");

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

    document.getElementById("editor-prompt-yes").click();

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

    vi.clearAllMocks();
  });

  it("restores the entire quiz", () => {
    const originalQuiz = structuredClone(
      JSON.parse(document.getElementById("app-data").textContent).quiz,
    );

    restoreQuizToDefault();

    document.getElementById("editor-prompt-yes").click();

    expect(state.quiz).toEqual(originalQuiz);
    expect(setQuizTitle).toHaveBeenCalledWith(originalQuiz.title);
    expect(removeAllLocalEdits).toHaveBeenCalled();
  });
});

describe("restartQuiz", () => {
  beforeEach(() => {
    state.quiz = {
      questions: [{}, {}, {}],
    };

    state.quizStorageKey = "test-quiz";
    state.currentQuestionIndex = 2;
    state.answerRevealed = true;
    state.wrongAnswerCount = 3;
    state.questionResults = ["correct", "wrong", "correct"];
    state.questionAnswers = [0, 1, 2];

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

  it("resets the quiz state and returns to the first question", () => {
    restartQuiz();

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

    expect(renderQuiz).toHaveBeenCalled();
  });
});
