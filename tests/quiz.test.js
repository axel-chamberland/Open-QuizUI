/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, beforeEach, vi } from "vitest";

import {
  handleAnswer,
  revealAnswer,
  setQuizTitle,
} from "../frontend/src/quiz.js";

vi.mock("../frontend/src/rendering/mcq.js", () => ({
  renderMCQ: vi.fn(),
  showExplanation: vi.fn(),
}));

vi.mock("../frontend/src/persistence/progress.js", () => ({
  setStoredQuestionIndex: vi.fn(),
}));

vi.mock("../frontend/src/rendering/flashcards.js", () => ({
  renderFlashcard: vi.fn(),
}));

vi.mock("../frontend/src/rendering/results.js", () => ({
  renderResults: vi.fn(),
}));

import { goTo } from "../frontend/src/quiz.js";
import { state } from "../frontend/src/state.js";
import { renderMCQ, showExplanation } from "../frontend/src/rendering/mcq.js";
import { setStoredQuestionIndex } from "../frontend/src/persistence/progress.js";
import { renderFlashcard } from "../frontend/src/rendering/flashcards.js";
import { renderResults } from "../frontend/src/rendering/results.js";
describe("goTo", () => {
  beforeEach(() => {
    document.body.innerHTML = `
  <div id="question-box">
    <input class="question-number" />
  </div>

  <div id="flashcard-box">
    <div class="flashcard-question"></div>
    <div class="flashcard-answer"></div>
  </div>
`;

    state.mode = "mcq";
    state.quiz = {
      questions: [
        { options: ["A", "B", "C"], correct_index: 0 },
        { options: ["A", "B", "C"], correct_index: 0 },
        { options: ["A", "B", "C"], correct_index: 0 },
        { options: ["A", "B", "C"], correct_index: 0 },
        { options: ["A", "B", "C"], correct_index: 0 },
      ],
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
    expect(document.querySelector(".question-number").value).toBe("3");

    expect(setStoredQuestionIndex).toHaveBeenCalledWith("test-quiz", 2);
    expect(document.getElementById("question-box").style.display).toBe("");
    expect(document.getElementById("flashcard-box").style.display).toBe("none");
    expect(renderMCQ).toHaveBeenCalled();
  });

  it("clamps to the first question", () => {
    goTo(-10);

    expect(state.currentQuestionIndex).toBe(0);
  });

  it("goes to the results page", () => {
    goTo(state.quiz.questions.length);

    expect(state.currentQuestionIndex).toBe(state.quiz.questions.length);
    expect(renderResults).toHaveBeenCalled();
  });

  it("renders MCQ when the question has at least two distractors", () => {
    state.mode = "mcq";

    goTo(2);

    expect(renderMCQ).toHaveBeenCalled();
    expect(renderFlashcard).not.toHaveBeenCalled();
    expect(state.mode).toBe("mcq");
  });

  it("falls back to flashcard when MCQ has a single distractor (choice)", () => {
    state.mode = "mcq";
    state.quiz.questions[2] = {
      options: ["A", "B"],
      correct_index: 0,
    };

    goTo(2);
    expect(document.getElementById("question-box").style.display).toBe("none");
    expect(document.getElementById("flashcard-box").style.display).toBe("");
    expect(renderMCQ).not.toHaveBeenCalled();
    expect(renderFlashcard).toHaveBeenCalled();
    expect(state.mode).toBe("mcq");
  });

  it("renders flashcard directly in flashcard mode", () => {
    state.mode = "flashcard";

    goTo(2);

    expect(document.getElementById("question-box").style.display).toBe("none");
    expect(document.getElementById("flashcard-box").style.display).toBe("");
    expect(renderFlashcard).toHaveBeenCalled();
    expect(renderMCQ).not.toHaveBeenCalled();
    expect(state.mode).toBe("flashcard");
  });
});

describe("setQuizTitle", () => {
  beforeEach(() => {
    document.body.innerHTML = `<div id="title"></div>`;
  });

  it("sets the document and visible title", () => {
    setQuizTitle("My Quiz");

    expect(document.title).toBe("My Quiz");
    document.querySelectorAll(".title").forEach((e) => {
      expect(e.textContent).toBe("My Quiz");
    });
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
    <div id="question-box"></div>

    <div id="flashcard-box" style="display: none">
      <div class="flashcard-answer"></div>
    </div>

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

    state.mode == "mcq";

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
  <div id="question-box"></div>

  <div id="flashcard-box" style="display: none">
    <div class="flashcard-answer"></div>
  </div>

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
