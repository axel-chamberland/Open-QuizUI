/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, beforeEach, vi } from "vitest";

import {
  clampQuestionIndex,
  handleAnswer,
  revealAnswer,
  setQuizTitle,
} from "../frontend/src/quiz.js";

describe("clampQuestionIndex", () => {
  it("returns the index when it is valid", () => {
    expect(clampQuestionIndex(2, 5)).toBe(2);
  });

  it("clamps negative indexes to 0", () => {
    expect(clampQuestionIndex(-1, 5)).toBe(0);
  });

  it("clamps indexes above the last question", () => {
    expect(clampQuestionIndex(10, 5)).toBe(4);
  });

  it("returns 0 when there is one question", () => {
    expect(clampQuestionIndex(0, 1)).toBe(0);
  });
});

vi.mock("../frontend/src/rendering/mcq.js", () => ({
  renderQuiz: vi.fn(),
  showExplanation: vi.fn(),
}));

vi.mock("../frontend/src/persistence/progress.js", () => ({
  setStoredQuestionIndex: vi.fn(),
}));

import { goTo } from "../frontend/src/quiz.js";
import { state } from "../frontend/src/state.js";
import { renderQuiz, showExplanation } from "../frontend/src/rendering/mcq.js";
import { setStoredQuestionIndex } from "../frontend/src/persistence/progress.js";
describe("goTo", () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <input id="question-number" />
    `;

    state.quiz = {
      questions: [{}, {}, {}, {}, {}],
    };

    state.quizStorageKey = "test-quiz";
    state.currentQuestionIndex = 0;
    state.answerRevealed = true;

    vi.clearAllMocks();
  });

  it("changes to the requested question", () => {
    goTo(2);

    expect(state.currentQuestionIndex).toBe(2);
    expect(state.answerRevealed).toBe(false);
    expect(document.getElementById("question-number").value).toBe("3");

    expect(setStoredQuestionIndex).toHaveBeenCalledWith("test-quiz", 2);

    expect(renderQuiz).toHaveBeenCalled();
  });

  it("clamps to the first question", () => {
    goTo(-10);

    expect(state.currentQuestionIndex).toBe(0);
  });

  it("clamps to the last question", () => {
    goTo(100);

    expect(state.currentQuestionIndex).toBe(4);
  });
});

describe("setQuizTitle", () => {
  beforeEach(() => {
    document.body.innerHTML = `<div id="title"></div>`;
  });

  it("sets the document and visible title", () => {
    setQuizTitle("My Quiz");

    expect(document.title).toBe("My Quiz");
    expect(document.getElementById("title").textContent).toBe("My Quiz");
  });

  it("limits the document title to 60 characters", () => {
    setQuizTitle("a".repeat(100));

    expect(document.title).toHaveLength(60);
  });
});

import { UNANSWERED, CORRECT, WRONG, SKIPPED } from "../frontend/src/state.js";
describe("revealAnswer", () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <div id="options">
        <button></button>
        <button></button>
        <button></button>
      </div>
    `;

    state.currentQuestionIndex = 0;
    state.quiz = {
      questions: [
        {
          correct_index: 1,
          options: ["A", "B", "C"],
        },
      ],
    };

    state.questionResults = [UNANSWERED];

    vi.clearAllMocks();
  });

  it("reveals the answer", () => {
    revealAnswer();

    expect(state.answerRevealed).toBe(true);
    expect(state.currentQuestion).toBe(state.quiz.questions[0]);
  });

  it("marks an unanswered question as skipped", () => {
    revealAnswer();

    expect(state.questionResults[0]).toBe(SKIPPED);
  });

  it("highlights the correct option", () => {
    revealAnswer();

    const buttons = document.querySelectorAll("#options button");

    expect(buttons[1].classList.contains("correct")).toBe(true);
  });
});

describe("handleAnswer", () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <div id="options">
        <button></button>
        <button></button>
        <button></button>
      </div>
    `;

    state.currentQuestionIndex = 0;
    state.currentQuestion = {
      correct_index: 1,
      options: ["A", "B", "C"],
    };
    state.questionResults = [UNANSWERED];
    state.questionAnswers = [null];
    state.wrongAnswerCount = 0;
    state.optionButtons = document.querySelectorAll("#options button");

    vi.clearAllMocks();
  });

  it("handles a correct answer", () => {
    const button = state.optionButtons[1];

    handleAnswer(1, button);

    expect(button.classList.contains("correct")).toBe(true);
    expect(button.disabled).toBe(true);
    expect(state.answerRevealed).toBe(true);
    expect(state.questionResults[0]).toBe(CORRECT);
    expect(state.questionAnswers[0]).toBe(1);

    expect(showExplanation).toHaveBeenCalledWith(state.currentQuestion);
  });

  it("disables all options after a correct answer", () => {
    handleAnswer(1, state.optionButtons[1]);

    state.optionButtons.forEach((button) => {
      expect(button.disabled).toBe(true);
    });
  });

  it("handles a wrong answer", () => {
    const button = state.optionButtons[0];

    handleAnswer(0, button);

    expect(button.classList.contains("wrong")).toBe(true);
    expect(button.disabled).toBe(true);
    expect(state.questionResults[0]).toBe(WRONG);
    expect(state.questionAnswers[0]).toBe(0);
    expect(state.wrongAnswerCount).toBe(1);
  });

  it("does not overwrite the first wrong answer", () => {
    handleAnswer(0, state.optionButtons[0]);
    handleAnswer(2, state.optionButtons[2]);

    expect(state.questionAnswers[0]).toBe(0);
  });
});
