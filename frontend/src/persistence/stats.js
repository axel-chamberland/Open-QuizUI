import { UNANSWERED, state } from "../state.js";

function getStatsKey(quizStorageKey) {
    return `quizStats_${quizStorageKey}`;
}

export function loadStats() {
    try {
        const data = JSON.parse(localStorage.getItem(getStatsKey(state.quizStorageKey)));

        if (Array.isArray(data?.results)) {
            state.questionResults = data.results;
        }

        if (Array.isArray(data?.answers)) {
            state.questionAnswers = data.answers;
        }

        if (data?.startDate) {
            state.defaultStartDate = data.startDate;
        }
    } catch {
        state.questionResults = new Array(state.quiz.questions.length).fill(UNANSWERED);
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
    } catch { }
}
