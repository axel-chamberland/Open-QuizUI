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
import { goToPosition, prevQuestion } from "../frontend/src/quiz.js";
import { addQuestion, deleteQuestion } from "../frontend/src/quiz.js";
import { toggleSRS } from "../frontend/src/quiz.js";
import { state } from "../frontend/src/state.js";
import { renderMCQ } from "../frontend/src/rendering/mcq.js";
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
    state.questionOrder = [0, 1, 2, 3, 4];
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
      options: ["A"],
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

describe("goToPosition", () => {
  beforeEach(() => {
    document.body.innerHTML = `
  <div id="results" style="display: none"></div>

  <div id="question-box">
    <input class="question-number" />
  </div>

  <div id="flashcard-box" style="display: none">
    <div class="flashcard-question"></div>
    <div class="flashcard-answer"></div>
  </div>
`;

    state.mode = "mcq";
    state.srs = false;
    state.quiz = {
      title: "Test Quiz",
      questions: [
        { question: "A", options: ["A", "B", "C"], correct_index: 0 },
        { question: "B", options: ["A", "B", "C"], correct_index: 0 },
        { question: "C", options: ["A", "B", "C"], correct_index: 0 },
      ],
    };
    // The quiz's own order, with the third question moved to the front.
    state.questionOrder = [2, 0, 1];
    state.quizStorageKey = "test-quiz";
    state.currentQuestionIndex = 0;
    state.answerRevealed = true;

    vi.clearAllMocks();
  });

  it("moves to the question at the given position in the order", () => {
    goToPosition(1);

    expect(state.currentQuestionIndex).toBe(2);
    expect(document.querySelector(".question-number").value).toBe("1");
  });

  it("moves through positions, not indexes", () => {
    goToPosition(3);

    expect(state.currentQuestionIndex).toBe(1);
    expect(document.querySelector(".question-number").value).toBe("3");
  });

  it("jumps to the results page past the last question", () => {
    goToPosition(4);

    expect(state.currentQuestionIndex).toBe(state.quiz.questions.length);
    expect(renderResults).toHaveBeenCalled();
  });

  it("treats a number below the first question as the first", () => {
    goToPosition(0);

    expect(state.currentQuestionIndex).toBe(2);
    expect(document.querySelector(".question-number").value).toBe("1");
  });

  it("uses the question's own index in SRS mode", () => {
    state.srs = true;

    goToPosition(2);

    expect(state.currentQuestionIndex).toBe(1);
  });
});

describe("prevQuestion", () => {
  beforeEach(() => {
    document.body.innerHTML = `
  <div id="results" style="display: none"></div>

  <div id="question-box">
    <input class="question-number" />
  </div>

  <div id="flashcard-box" style="display: none"></div>
`;

    state.mode = "mcq";
    state.srs = false;
    state.quiz = {
      title: "Test Quiz",
      questions: [
        { question: "A", options: ["A", "B", "C"], correct_index: 0 },
        { question: "B", options: ["A", "B", "C"], correct_index: 0 },
        { question: "C", options: ["A", "B", "C"], correct_index: 0 },
      ],
    };
    // The quiz's own order, with the third question moved to the front.
    state.questionOrder = [2, 0, 1];
    state.quizStorageKey = "test-quiz";
    state.currentQuestionIndex = 0;
    state.answerRevealed = true;

    vi.clearAllMocks();
  });

  it("steps back through the order", () => {
    state.currentQuestionIndex = 1;

    prevQuestion();

    expect(state.currentQuestionIndex).toBe(0);
  });

  it("leaves the results page for the last question in the order", () => {
    // How the navigation field reaches it: the current index sits past
    // the last question, so it is not part of the order.
    state.currentQuestionIndex = state.quiz.questions.length;
    document.getElementById("results").style.display = "";

    prevQuestion();

    expect(state.currentQuestionIndex).toBe(1);
    expect(document.getElementById("results").style.display).toBe("none");
  });

  it("returns to the last question when the results page follows it", () => {
    // Stepping forward off the last question shows the results page
    // without moving the index, so back has to land on that same last
    // question, not the one before it.
    state.currentQuestionIndex = 1;
    document.getElementById("results").style.display = "";

    prevQuestion();

    expect(state.currentQuestionIndex).toBe(1);
    expect(document.getElementById("results").style.display).toBe("none");
  });

  it("does nothing on the first question of the order", () => {
    state.currentQuestionIndex = 2;

    prevQuestion();

    expect(state.currentQuestionIndex).toBe(2);
  });
});

describe("toggleSRS", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
    localStorage.clear();

    state.quiz = {
      questions: [
        { options: ["A", "B", "C"], correct_index: 0 },
        { options: ["A", "B", "C"], correct_index: 0 },
        { options: ["A", "B", "C"], correct_index: 0 },
      ],
    };
    state.questionOrder = [0, 1, 2];
    state.quizStorageKey = "test-quiz";
    state.currentQuestionIndex = 2;
    state.srs = true;

    vi.clearAllMocks();
  });

  it("persists the current position when turning SRS off", async () => {
    // Questions on a specific position that must survive a refresh
    await toggleSRS();

    expect(state.srs).toBe(false);
    expect(setStoredQuestionIndex).toHaveBeenCalledWith("test-quiz", 2);
    expect(JSON.parse(localStorage.getItem("appDataOverrides_test-quiz"))).toEqual(
      { srsOnLoad: false },
    );
    expect(document.body.classList.contains("srs-mode")).toBe(false);
  });

  it("switches the field from the question's index to its position", async () => {
    document.body.innerHTML = `<input class="question-number" />`;

    // The question's own index, as SRS mode shows it.
    state.questionOrder = [2, 0, 1];
    state.currentQuestionIndex = 2;
    document.querySelector(".question-number").value = "3";

    await toggleSRS();

    expect(document.querySelector(".question-number").value).toBe("1");
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

    state.currentQuestion = state.quiz.questions[0];

    state.mode = "mcq";

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

const THREE_QUESTION_QUIZ = {
  title: "Test Quiz",
  questions: [
    { question: "Q1", options: ["A", "B"], correct_index: 0 },
    { question: "Q2", options: ["A", "B"], correct_index: 0 },
    { question: "Q3", options: ["A", "B"], correct_index: 0 },
  ],
};

describe("addQuestion", () => {
  beforeEach(() => {
    localStorage.clear();

    document.body.innerHTML = `
  <script id="app-data" type="application/json">${JSON.stringify({ quiz: THREE_QUESTION_QUIZ })}</script>
  <input class="question-number" />
  <span class="question-count"></span>
`;

    state.mode = "mcq";
    state.srs = false;
    state.quiz = structuredClone(THREE_QUESTION_QUIZ);
    state.quizStorageKey = "test-quiz";
    state.builtInQuestionCount = THREE_QUESTION_QUIZ.questions.length;
    state.removedQuestions = new Set();
    state.questionOrder = [0, 1, 2];
    state.questionResults = [];
    state.questionAnswers = [];
    state.currentQuestionIndex = 0;

    vi.clearAllMocks();
  });

  it("appends the question last", () => {
    const index = addQuestion();

    expect(index).toBe(3);
    expect(state.questionOrder).toEqual([0, 1, 2, 3]);
    expect(state.quiz.questions[3]).toEqual({
      question: "",
      options: ["", ""],
      correct_index: 0,
      explanation: "",
    });
  });

  it("puts the question before another one", () => {
    addQuestion(1);

    expect(state.questionOrder).toEqual([0, 3, 1, 2]);
  });

  it("puts the question right after another one", () => {
    addQuestion(2);

    expect(state.questionOrder).toEqual([0, 1, 3, 2]);
  });

  it("persists the question and the slot it was put in", () => {
    addQuestion(1);

    expect(JSON.parse(localStorage.getItem("quizEdits_test-quiz"))[3]).toEqual(
      state.quiz.questions[3],
    );
    expect(localStorage.getItem("questionOrder_test-quiz")).toBe(
      JSON.stringify([0, 3, 1, 2]),
    );
  });
});

describe("deleteQuestion", () => {
  beforeEach(() => {
    localStorage.clear();

    document.body.innerHTML = `
  <script id="app-data" type="application/json">${JSON.stringify({ quiz: THREE_QUESTION_QUIZ })}</script>
  <input class="question-number" />
  <span class="question-count"></span>
`;

    state.mode = "mcq";
    state.srs = false;
    state.quiz = structuredClone(THREE_QUESTION_QUIZ);
    state.quizStorageKey = "test-quiz";
    state.builtInQuestionCount = THREE_QUESTION_QUIZ.questions.length;
    state.removedQuestions = new Set();
    state.questionOrder = [0, 1, 2];
    state.questionResults = [];
    state.questionAnswers = [];
    state.currentQuestionIndex = 0;

    vi.clearAllMocks();
  });

  it("deletes one of the quiz's own questions", () => {
    deleteQuestion(1);

    expect(state.questionOrder).toEqual([0, 2]);
    expect(state.removedQuestions.has(1)).toBe(true);

    // The quiz keeps the question: its index is what the stored state
    // is keyed on.
    expect(state.quiz.questions).toHaveLength(3);

    expect(localStorage.getItem("questionRemovals_test-quiz")).toBe("[1]");
    expect(localStorage.getItem("questionOrder_test-quiz")).toBe(
      JSON.stringify([0, 2]),
    );
  });

  it("drops the deleted question's stored edit", () => {
    localStorage.setItem(
      "quizEdits_test-quiz",
      JSON.stringify({ 1: { question: "edited" } }),
    );

    deleteQuestion(1);

    expect(localStorage.getItem("quizEdits_test-quiz")).toBeNull();
  });

  it("takes a question added in the editor back out", () => {
    const index = addQuestion();

    deleteQuestion(index);

    expect(state.quiz.questions).toHaveLength(3);
    expect(state.questionOrder).toEqual([0, 1, 2]);
    expect(state.removedQuestions.size).toBe(0);
    expect(localStorage.getItem("quizEdits_test-quiz")).toBeNull();
  });
});
