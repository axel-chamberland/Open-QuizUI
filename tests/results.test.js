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

/**
 * The "Your answer" of each correction, in the order they are shown.
 *
 * The template's newlines and indentation are collapsed first, so the
 * value can be read between its label and the next one.
 */
const correctionAnswers = () =>
  [...document.querySelectorAll("#question-corrections article")].map(
    (article) =>
      article.textContent
        .replace(/\s+/g, " ")
        .match(/Your answer: (.*?) Correct answer: /)?.[1],
  );

/** The outcome bar's key entries, as the label and count they show. */
const keyEntries = () =>
  [...document.querySelectorAll("#stats-chart .stats-bar-key li")].map((li) =>
    li.textContent.replace(/\s+/g, " ").trim(),
  );

/** The outcome bar's segments, as their classes, in the order drawn. */
const segments = () =>
  [...document.querySelectorAll("#stats-chart .stats-bar > div")].map(
    (segment) => segment.className,
  );

describe("renderResults", () => {
  beforeEach(() => {
    document.body.innerHTML = `
<div id="results"></div>
<div id="flashcard-box"></div>
<div id="question-box"></div>

<div id="score"></div>
<div id="accuracy"></div>
<div id="time"></div>
<div id="averageTime"></div>

<div id="stats-chart"></div>
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
    state.questionOrder = [0, 1, 2, 3];

    state.mode = "mcq";

    state.timer.visible = false;
    state.defaultStartDate = Date.now();

    vi.clearAllMocks();
  });

  it("displays the results", async () => {
    await renderResults();

    expect(document.getElementById("question-box").style.display).toBe("none");

    expect(document.getElementById("results").style.display).toBe("");
  });

  it("calculates the score and the outcome bar", async () => {
    await renderResults();

    expect(document.getElementById("score").textContent).toBe("Score: 1/2");

    expect(document.getElementById("accuracy").textContent).toBe(
      "Accuracy: 50.0%",
    );

    /* The key of the bar carries the four counts, in reading order. */
    expect(keyEntries()).toEqual([
      "Correct 1",
      "Wrong 1",
      "Skipped 1",
      "Unanswered 1",
    ]);

    expect(segments()).toEqual([
      "outcome-correct",
      "outcome-wrong",
      "outcome-skipped",
      "outcome-unanswered",
    ]);
  });

  it("leaves an outcome out of the bar that no question ended in", async () => {
    state.questionResults = [CORRECT, CORRECT, CORRECT, UNANSWERED];

    await renderResults();

    /* The bar skips it, the key still says it is empty. */
    expect(segments()).toEqual(["outcome-correct", "outcome-unanswered"]);

    expect(keyEntries()).toEqual([
      "Correct 3",
      "Wrong 0",
      "Skipped 0",
      "Unanswered 1",
    ]);

    expect(document.querySelectorAll(".stats-bar-key li.empty")).toHaveLength(
      2,
    );
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

  it("tells the picked option from a skip and from no answer", async () => {
    await renderResults();

    expect(correctionAnswers()).toEqual(["A", "A", "Unanswered", "Skipped"]);
  });

  it("shows the rating of a question that was rated, not picked", async () => {
    // Rating a question in spaced repetition mode answers it without
    // picking an option.
    state.questionAnswers = [null, null, null, null];

    await renderResults();

    expect(correctionAnswers()).toEqual(["✓", "✗", "Unanswered", "Skipped"]);
  });

  it("shows the checkmarks a flashcard is rated with", async () => {
    state.mode = "flashcard";

    await renderResults();

    expect(correctionAnswers()).toEqual(["✓", "✗", "Unanswered", "Unanswered"]);
  });
});
