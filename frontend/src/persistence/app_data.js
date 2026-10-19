import { hashQuiz } from "./progress.js";

/**
 * Loads the app data used to initialize the app.
 *
 * Reads the embedded #app-data payload first, then applies any overrides
 * the user made at runtime (stored per quiz like the other persisted
 * data) on top, so changes such as the quiz mode or enabled spaced
 * repetition survive a refresh.
 *
 * @returns {object} The app data to initialize the app with.
 */
export function loadAppData() {
  const appData = JSON.parse(document.getElementById("app-data").textContent);

  return { ...appData, ...getStoredAppDataOverrides(hashQuiz(appData.quiz)) };
}

function getAppDataOverridesKey(quizStorageKey) {
  return `appDataOverrides_${quizStorageKey}`;
}

/**
 * Returns the runtime overrides stored for the given quiz.
 *
 * @returns {object} Partial app data overriding the embedded payload.
 */
export function getStoredAppDataOverrides(quizStorageKey) {
  try {
    const data = JSON.parse(
      localStorage.getItem(getAppDataOverridesKey(quizStorageKey)),
    );

    if (data && typeof data === "object" && !Array.isArray(data)) {
      return data;
    }
  } catch {}

  return {};
}

/**
 * Persists runtime changes to the app data so they are restored on the
 * next load. Only app data fields that differ from the embedded payload
 * should be passed (e.g. mode, srsOnLoad, srsQueueSize, requestRetention).
 *
 * @param {number|null} quizStorageKey Quiz hash the overrides belong to.
 * @param {object} overrides Partial app data to merge into the overrides.
 */
export function saveAppDataOverrides(quizStorageKey, overrides) {
  if (!quizStorageKey) {
    return;
  }

  try {
    const stored = getStoredAppDataOverrides(quizStorageKey);

    localStorage.setItem(
      getAppDataOverridesKey(quizStorageKey),
      JSON.stringify({ ...stored, ...overrides }),
    );
  } catch {}
}
