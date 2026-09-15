/**
 * @vitest-environment jsdom
 */

import { beforeEach, describe, expect, vi, it } from "vitest";
import { renderResults } from "../frontend/src/rendering/results";
import {
  CORRECT,
  WRONG,
  SKIPPED,
  UNANSWERED,
  state,
} from "../frontend/src/state";

vi.mock("../frontend/src/persistence/progress.js", () => ({
  setStoredQuestionIndex: vi.fn(),
}));

vi.mock("../frontend/src/shared/formatting.js", () => ({
  formatTime: vi.fn((seconds) => `TIME:${seconds}`),
}));

vi.mock("../frontend/src/shared/markdown.js", () => ({
  renderMarkdown: vi.fn((text) => text),
}));

vi.mock("../frontend/src/timer.js", () => ({
  saveTimer: vi.fn(),
  updateTimer: vi.fn(),
}));

vi.mock("../frontend/src/rendering/mcq.js", () => ({
  renderQuiz: vi.fn(),
}));

describe("renderResults", () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <div class="question-box"></div>
      <div id="results" style="display: none"></div>

      <div id="score"></div>
      <div id="accuracy"></div>
      <div id="correct"></div>
      <div id="wrong"></div>
      <div id="unanswered"></div>
      <div id="skipped"></div>
      <div id="time"></div>
      <div id="averageTime"></div>

      <div id="statsChart"></div>
      <div id="question-corrections"></div>
    `;

    state.quiz = {
      questions: [
        {
          question: "Q1",
          options: ["A", "B"],
          correct_index: 0,
          explanation: "Explanation",
        },
        {
          question: "Q2",
          options: ["A", "B"],
          correct_index: 1,
        },
        {
          question: "Q3",
          options: ["A", "B"],
          correct_index: 0,
        },
        {
          question: "Q4",
          options: ["A", "B"],
          correct_index: 1,
        },
      ],
    };

    state.questionResults = [CORRECT, WRONG, UNANSWERED, SKIPPED];

    state.questionAnswers = [0, 0, null, null];

    state.timer.visible = false;
    state.defaultStartDate = Date.now();

    vi.clearAllMocks();
  });

  it("displays the results", async () => {
    await renderResults();

    expect(document.querySelector(".question-box").style.display).toBe("none");

    expect(document.getElementById("results").style.display).toBe("");
  });

  it("calculates and displays the score", async () => {
    await renderResults();

    expect(document.getElementById("score").textContent).toBe("Score: 1/2");

    expect(document.getElementById("accuracy").textContent).toBe(
      "Accuracy: 50.0%",
    );

    expect(document.getElementById("correct").textContent).toBe("Correct: 1");

    expect(document.getElementById("wrong").textContent).toBe("Wrong: 1");

    expect(document.getElementById("unanswered").textContent).toBe(
      "Unanswered: 1",
    );

    expect(document.getElementById("skipped").textContent).toBe("Skipped: 1");
  });

  it("shows the correction sheet", async () => {
    await renderResults();

    const corrections = document.getElementById("question-corrections");

    expect(corrections.querySelectorAll("article")).toHaveLength(4);
    expect(corrections.textContent).toContain("Question 1");
    expect(corrections.textContent).toContain("Your answer:");
    expect(corrections.textContent).toContain("Correct answer:");
    expect(corrections.textContent).toContain("Explanation");
  });
});
