import { initializeState } from "./state.js";
import { initializeEvents } from "./ui/events.js";
import { loadAppData } from "./persistence/app_data.js";
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
  toggleSRS,
} from "./quiz.js";

const appData = loadAppData();

export const ENABLE_MATHJAX = appData.enableMathJax;
export const quiz = appData.quiz;
export const mode = appData.mode;

/*
 * Open WebUI sizes the hosting iframe from the height this page reports.
 * The results page lists every correction, so on its own it would make the
 * message (and the whole chat page) as tall as the corrections are long:
 * the embedded class caps the results column and lets it scroll instead.
 */
if (window.self !== window.top) {
  document.body.classList.add("embedded");
}

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

state.srsQueueSize = appData.srsQueueSize;

/*
 * FSRS scheduler parameters.
 *
 * Per-quiz overrides (already merged into appData) carry the config
 * set in the editor; requestRetention in the embedded payload remains
 * the fallback when no editor config exists.
 */
Object.assign(state.srsConfig, appData.srsConfig ?? {});
if (appData.srsConfig === undefined) {
  state.srsConfig.request_retention = appData.requestRetention;
}

loadStats();

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

  // Enable spaced repetition on startup if requested (via the app data)
  if (appData.srsOnLoad) {
    await toggleSRS();
  }
}

if (document.readyState === "loading") {
  window.addEventListener("load", initializeApp, { once: true });
} else {
  initializeApp();
  document.body.classList.remove("app-loading");
}
