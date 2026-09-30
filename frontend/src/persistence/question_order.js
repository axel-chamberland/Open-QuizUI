export function loadQuestionOrder(quizStorageKey, questionCount) {
  try {
    const data = JSON.parse(
      localStorage.getItem(`questionOrder_${quizStorageKey}`),
    );

    if (Array.isArray(data)) {
      return data;
    }
  } catch {}

  return Array.from({ length: questionCount }, (_, index) => index);
}

export function saveQuestionOrder(quizStorageKey, questionOrder) {
  try {
    localStorage.setItem(
      `questionOrder_${quizStorageKey}`,
      JSON.stringify(questionOrder),
    );
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
