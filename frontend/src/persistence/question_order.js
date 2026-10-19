/**
 * Loads the question order stored for a quiz.
 *
 * The stored order is normalized against the quiz: indexes that no
 * longer exist are dropped, and questions missing from it - such as
 * ones added in the editor - are appended in their natural order, so
 * every question stays reachable. Questions deleted locally are left
 * out instead, or normalizing would bring them back.
 *
 * @param {string} quizStorageKey
 * @param {number} questionCount
 * @param {Set<number>} [removedIndexes] Deleted question indexes.
 * @returns {number[]} Order of question indexes.
 */
export function loadQuestionOrder(
  quizStorageKey,
  questionCount,
  removedIndexes = null,
) {
  const removed = removedIndexes ?? new Set();

  let stored = null;

  try {
    const data = JSON.parse(
      localStorage.getItem(`questionOrder_${quizStorageKey}`),
    );

    if (Array.isArray(data)) {
      stored = data;
    }
  } catch {}

  if (!stored) {
    return Array.from({ length: questionCount }, (_, index) => index).filter(
      (index) => !removed.has(index),
    );
  }

  const order = [];
  const seen = new Set();

  for (const index of stored) {
    const valid =
      Number.isInteger(index) &&
      index >= 0 &&
      index < questionCount &&
      !seen.has(index) &&
      !removed.has(index);

    if (valid) {
      seen.add(index);
      order.push(index);
    }
  }

  for (let index = 0; index < questionCount; index++) {
    if (!seen.has(index) && !removed.has(index)) {
      order.push(index);
    }
  }

  return order;
}

export function saveQuestionOrder(quizStorageKey, questionOrder) {
  try {
    localStorage.setItem(
      `questionOrder_${quizStorageKey}`,
      JSON.stringify(questionOrder),
    );
  } catch {}
}

export function clearQuestionOrder(quizStorageKey) {
  try {
    localStorage.removeItem(`questionOrder_${quizStorageKey}`);
  } catch {}
}

export function loadQuestionSRSState(quizStorageKey) {
  try {
    const data = JSON.parse(
      localStorage.getItem(`questionSRSQueue_${quizStorageKey}`),
    );

    if (data && typeof data === "object" && Array.isArray(data.queue)) {
      return {
        score: data.score ?? 0,
        queue: data.queue,
      };
    }
  } catch {}

  return null;
}

export function saveQuestionSRSState(quizStorageKey, srsState) {
  try {
    localStorage.setItem(
      `questionSRSQueue_${quizStorageKey}`,
      JSON.stringify(srsState),
    );
  } catch {}
}

export function resetQuestionSRSState(quizStorageKey) {
  try {
    localStorage.removeItem(`questionSRSQueue_${quizStorageKey}`);
  } catch {}
}
