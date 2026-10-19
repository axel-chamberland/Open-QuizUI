/**
 * @vitest-environment jsdom
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  getCurrentQuestionArrayIndex,
  nextQuestion,
} from "../frontend/src/quiz.js";
import { rateFlashcard } from "../frontend/src/rendering/flashcards.js";
import { CORRECT, UNANSWERED, WRONG, state } from "../frontend/src/state.js";

vi.mock("../frontend/src/quiz.js", () => ({
  getCurrentQuestionArrayIndex: vi.fn(() => 0),
  nextQuestion: vi.fn(),
  renderQuestion: vi.fn(),
  updateNavigation: vi.fn(),
}));

vi.mock("../frontend/src/shared/markdown.js", () => ({
  renderMarkdown: vi.fn((text) => text),
}));

vi.mock("../frontend/src/shared/mathjax.js", () => ({
  typesetMath: vi.fn(),
}));

vi.mock("../frontend/src/persistence/stats.js", () => ({
  saveStats: vi.fn(),
}));

describe("rateFlashcard", () => {
  beforeEach(() => {
    vi.mocked(getCurrentQuestionArrayIndex).mockReturnValue(1);
    vi.mocked(nextQuestion).mockClear();

    state.questionResults = [UNANSWERED, UNANSWERED];
    state.answerRevealed = true;
  });

  it("records a card rated unknown as wrong", async () => {
    await rateFlashcard(false);

    expect(state.questionResults[1]).toBe(WRONG);
    expect(nextQuestion).toHaveBeenCalled();
  });

  it("records a card rated known as correct", async () => {
    await rateFlashcard(true);

    expect(state.questionResults[1]).toBe(CORRECT);
    expect(nextQuestion).toHaveBeenCalled();
  });

  it("shows the rating in the corner of the page", async () => {
    document.body.innerHTML = '<div id="rating-indicator"></div>';

    await rateFlashcard(false);

    expect(document.getElementById("rating-indicator").textContent).toBe("✗");

    await rateFlashcard(true);

    expect(document.getElementById("rating-indicator").textContent).toBe("✓");
  });

  it("ignores a rating before the answer is revealed", async () => {
    state.answerRevealed = false;

    await rateFlashcard(false);

    expect(state.questionResults[1]).toBe(UNANSWERED);
    expect(nextQuestion).not.toHaveBeenCalled();
  });
});
