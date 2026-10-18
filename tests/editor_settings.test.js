/**
 * @vitest-environment jsdom
 */
import { readFileSync } from "node:fs";
import { describe, it, beforeEach, expect, vi } from "vitest";
import { state } from "../frontend/src/state.js";

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

// editor.js re-initializes the SRS scheduler when the additional
// settings change, which would load FSRS from the CDN.
vi.mock("../frontend/src/srs.js", async () => {
  const actual = await vi.importActual("../frontend/src/srs.js");

  return {
    ...actual,
    initSRS: vi.fn(async () => true),
  };
});

// editor.js has a top-level event listener, so the required DOM must exist
// before importing it.
document.documentElement.innerHTML =
  indexHtml.match(/<html[^>]*>([\s\S]*)<\/html>/i)?.[1] ?? indexHtml;

const { openEditor, saveEdit } = await import(
  "../frontend/src/rendering/editor.js"
);

const { saveLocalEdit } = await import(
  "../frontend/src/persistence/quiz_edits.js"
);

const { initSRS } = await import("../frontend/src/srs.js");

function promptMessage() {
  const element = document.getElementById("global-prompt");

  return element.classList.contains("visible")
    ? document.getElementById("global-prompt-message").textContent
    : null;
}

describe("saveEdit with the additional settings", () => {
  beforeEach(() => {
    localStorage.clear();

    document.getElementById("app-data").textContent = JSON.stringify({
      quiz: {
        title: "Quiz",
        questions: [
          {
            question: "Question 1",
            options: ["A", "B"],
            correct_index: 0,
          },
        ],
      },
    });

    state.quizStorageKey = "test-quiz";
    state.currentQuestionIndex = 0;
    state.quiz = {
      title: "Quiz",
      questions: [
        {
          question: "Question 1",
          options: ["A", "B"],
          correct_index: 0,
        },
      ],
    };

    state.srs = true;
    state.srsQueueSize = 20;
    state.questionSRSQueue = [];

    openEditor();

    vi.clearAllMocks();
  });

  it("alerts when only the settings changed", async () => {
    saveLocalEdit.mockReturnValue(false);

    document.getElementById("editor-srs-queue-size").value = "5";

    await saveEdit();

    expect(promptMessage()).toBe("Changes saved.");
  });

  it("re-initializes SRS when the queue size changed", async () => {
    document.getElementById("editor-srs-queue-size").value = "5";

    await saveEdit();

    expect(state.srsQueueSize).toBe(5);
    expect(initSRS).toHaveBeenCalledWith("test-quiz", 0);
  });

  it("does not re-initialize when the settings are unchanged", async () => {
    await saveEdit();

    expect(initSRS).not.toHaveBeenCalled();
  });

  it("does not re-initialize when SRS is off", async () => {
    state.srs = false;

    openEditor();
    vi.clearAllMocks();

    document.getElementById("editor-srs-queue-size").value = "5";

    await saveEdit();

    expect(initSRS).not.toHaveBeenCalled();
    expect(state.srsQueueSize).toBe(5);
  });
});
