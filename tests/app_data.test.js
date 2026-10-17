/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, beforeEach } from "vitest";

import { hashQuiz } from "../frontend/src/persistence/progress.js";
import {
  loadAppData,
  getStoredAppDataOverrides,
  saveAppDataOverrides,
} from "../frontend/src/persistence/app_data.js";

const APP_DATA = {
  mode: "mcq",
  enableMathJax: true,
  srsQueueSize: 20,
  requestRetention: 0.9,
  srsOnLoad: false,
  quiz: {
    title: "Test Quiz",
    questions: [
      { question: "What is 2 + 2?", answer: "4", distractors: ["3", "5"] },
    ],
  },
};

function embedAppData(appData) {
  document.body.innerHTML = `<script id="app-data" type="application/json">${JSON.stringify(
    appData,
  )}</script>`;
}

const QUIZ_KEY = hashQuiz(APP_DATA.quiz);

describe("loadAppData", () => {
  beforeEach(() => {
    localStorage.clear();
    embedAppData(APP_DATA);
  });

  it("returns the embedded app data when there are no overrides", () => {
    expect(loadAppData()).toEqual(APP_DATA);
  });

  it("returns an empty override object for an unknown quiz", () => {
    expect(getStoredAppDataOverrides(QUIZ_KEY + 1)).toEqual({});
  });

  it("stores the overrides for the quiz", () => {
    saveAppDataOverrides(QUIZ_KEY, { mode: "flashcard", srsOnLoad: true });

    expect(getStoredAppDataOverrides(QUIZ_KEY)).toEqual({
      mode: "flashcard",
      srsOnLoad: true,
    });
  });

  it("merges new overrides into previously stored ones", () => {
    saveAppDataOverrides(QUIZ_KEY, { mode: "flashcard" });
    saveAppDataOverrides(QUIZ_KEY, { srsOnLoad: true, srsQueueSize: 5 });

    const appData = loadAppData();

    expect(appData.mode).toBe("flashcard");
    expect(appData.srsOnLoad).toBe(true);
    expect(appData.srsQueueSize).toBe(5);
  });

  it("keeps keys that are not overridden", () => {
    saveAppDataOverrides(QUIZ_KEY, { mode: "flashcard" });

    const appData = loadAppData();

    expect(appData.srsOnLoad).toBe(APP_DATA.srsOnLoad);
    expect(appData.requestRetention).toBe(APP_DATA.requestRetention);
    expect(appData.quiz).toEqual(APP_DATA.quiz);
  });

  it("per-quiz overrides do not leak into other quizzes", () => {
    saveAppDataOverrides(QUIZ_KEY, { mode: "mcq" });

    const otherQuiz = {
      ...APP_DATA,
      mode: "flashcard",
      quiz: { title: "Other quiz", questions: [] },
    };
    embedAppData(otherQuiz);

    // No override exists for the other quiz: its own app data wins.
    expect(loadAppData().mode).toBe(otherQuiz.mode);
  });
});
