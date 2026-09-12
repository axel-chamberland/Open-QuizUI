import { state } from "../state.js";

export function hashQuiz(quiz) {
    // Hash derived from the quiz's content to avoid overlap
    const data = JSON.stringify(quiz);

    let hash = 0;
    for (let i = 0; i < data.length; i++) {
        hash = (hash << 5) - hash + data.charCodeAt(i);
        hash |= 0;
    }

    return hash >>> 0;
}

function getProgressKey(quizStorageKey) {
    return `currentQuestionIndex_${quizStorageKey}`;
}

export function getStoredQuestionIndex(quizStorageKey) {
    try {
        const index = Number(
            localStorage.getItem(getProgressKey(quizStorageKey)),
        );

        if (!Number.isInteger(index)) {
            return 0;
        }

        return Math.max(0, Math.min(index, state.quiz.questions.length - 1));
    } catch {
        return 0;
    }
}


export function setStoredQuestionIndex(quizStorageKey, value) {
    try {
        localStorage.setItem(
            getProgressKey(quizStorageKey),
            String(value),
        );
    } catch { }
}

