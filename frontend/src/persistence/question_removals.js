/**
 * Persistence for the quiz's own questions deleted in the editor.
 *
 * A deleted question is not taken out of the quiz array: the quiz's own
 * questions are the baseline that every stored edit, result, order
 * entry and SRS card is keyed against, so their indexes have to stay
 * put. The deletion is recorded here instead, and the index is left out
 * of the navigation order.
 */

function getQuestionRemovalsKey(quizStorageKey) {
  return `questionRemovals_${quizStorageKey}`;
}

/**
 * Loads the indexes of the quiz's own questions deleted locally.
 *
 * @param {string} quizStorageKey
 * @returns {Set<number>} Deleted question indexes.
 */
export function loadQuestionRemovals(quizStorageKey) {
  try {
    const data = JSON.parse(
      localStorage.getItem(getQuestionRemovalsKey(quizStorageKey)),
    );

    if (Array.isArray(data)) {
      return new Set(data.filter(Number.isInteger));
    }
  } catch {}

  return new Set();
}

/**
 * Saves the indexes of the quiz's own questions deleted locally.
 *
 * @param {string} quizStorageKey
 * @param {Set<number>} indexes Deleted question indexes.
 * @returns {void}
 */
export function saveQuestionRemovals(quizStorageKey, indexes) {
  const key = getQuestionRemovalsKey(quizStorageKey);

  try {
    if (indexes.size === 0) {
      localStorage.removeItem(key);
      return;
    }

    localStorage.setItem(key, JSON.stringify(Array.from(indexes)));
  } catch {}
}

/**
 * Forgets the locally deleted questions.
 *
 * @param {string} quizStorageKey
 * @returns {void}
 */
export function clearQuestionRemovals(quizStorageKey) {
  try {
    localStorage.removeItem(getQuestionRemovalsKey(quizStorageKey));
  } catch {}
}
