import { initializeState } from "./state.js";
import { initializeEvents } from "./ui/events.js";
import { loadQuizEdits } from "./persistence/quiz_edits.js";
import { loadStats } from "./persistence/stats.js";
import { loadMathJax } from "./shared/mathjax.js";
import { state } from "./state.js";
import { initHeightReporting } from "./ui/reportHeight.js";
import {
  setMode,
  goTo,
  setQuizTitle,
  updateQuestionCounts,
  updateQuestionNumbers,
} from "./quiz.js";

const appData = JSON.parse(document.getElementById("app-data").textContent);

export const ENABLE_MATHJAX = appData.enableMathJax;
export const quiz = appData.quiz;
export const mode = appData.mode;

// In case the iframe was reset while in fullscreen, reload the page to reset affected elements
// This mainly happens when you call the action function on another device while being in pseudo-fullscreen,
// causing the iframe to reset without exiting pseudo-fullscreen
try {
  if (window.top.document.body.classList.contains("pseudo-fullscreen-active")) {
    window.top.location.reload();
  }
} catch {
  // The iframe may not be permitted to access the top document
  // when origin restrictions are disabled.
  // This is fine, since it means that pseudo-fullscreen did not modify anything that needs to be reset
}

initializeState(quiz);
loadStats();
loadQuizEdits(state);

async function initializeApp() {
  await loadMathJax(ENABLE_MATHJAX);

  if (state.mathReady && window.MathJax?.startup?.promise) {
    await window.MathJax.startup.promise;
  }

  setQuizTitle(quiz.title);
  initializeEvents();
  initHeightReporting();
  updateQuestionCounts();
  updateQuestionNumbers();

  setMode(appData.mode);
  goTo(state.currentQuestionIndex);
}

if (document.readyState === "loading") {
  window.addEventListener("load", initializeApp, { once: true });
} else {
  initializeApp();
  document.body.classList.remove("app-loading");
}
