import { UNANSWERED, state } from "../state.js";

function getStatsKey(quizStorageKey) {
  return `quizStats_${quizStorageKey}`;
}

/**
 * Pads a stored per-question array to the quiz's current length.
 *
 * Questions added in the editor are stored past the end of the quiz,
 * so the saved results can be shorter than the quiz on load.
 *
 * @param {Array} values Stored per-question values.
 * @param {*} fallback Value for questions the store does not cover.
 * @returns {Array} Array covering every question.
 */
function padToQuestionCount(values, fallback) {
  const padded = values.slice(0, state.quiz.questions.length);

  while (padded.length < state.quiz.questions.length) {
    padded.push(fallback);
  }

  return padded;
}

export function loadStats() {
  try {
    const data = JSON.parse(
      localStorage.getItem(getStatsKey(state.quizStorageKey)),
    );

    if (Array.isArray(data?.results)) {
      state.questionResults = padToQuestionCount(data.results, UNANSWERED);
    }

    if (Array.isArray(data?.answers)) {
      state.questionAnswers = padToQuestionCount(data.answers, null);
    }

    if (data?.startDate) {
      state.defaultStartDate = data.startDate;
    }
  } catch {
    state.questionResults = new Array(state.quiz.questions.length).fill(
      UNANSWERED,
    );
    state.questionAnswers = new Array(state.quiz.questions.length).fill(null);
    state.defaultStartDate = Date.now();
  }
}

export function saveStats() {
  try {
    localStorage.setItem(
      getStatsKey(state.quizStorageKey),
      JSON.stringify({
        results: state.questionResults,
        answers: state.questionAnswers,
        startDate: state.defaultStartDate,
      }),
    );
  } catch {}
}
