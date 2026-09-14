import { state } from "../state.js";

function getQuizEditsKey(quizStorageKey) {
    return `quizEdits_${quizStorageKey}`;
}

export function saveLocalEdit(index, titleChanged) {
    const key = getQuizEditsKey(state.quizStorageKey);

    let edits = {};

    try {
        edits = JSON.parse(localStorage.getItem(key)) || {};
    } catch {
        edits = {};
    }

    if (titleChanged) {
        edits.title = state.quiz.title;
    }

    edits[index] = state.quiz.questions[index];

    try {
        localStorage.setItem(key, JSON.stringify(edits));
        console.log("Saved edit:", key, edits);
        return true;
    } catch (e) {
        console.error("Failed to save edit:", e);
        return false;
    }
}

export function loadQuizEdits(state) {
    const key = getQuizEditsKey(state.quizStorageKey);

    try {
        const edits = JSON.parse(localStorage.getItem(key));

        if (!edits) {
            return;
        }

        if (edits.title !== undefined) {
            state.quiz.title = edits.title;
        }

        // Load edited questions
        for (const [index, question] of Object.entries(edits)) {
            const i = Number(index);
            if (Number.isInteger(i) && i >= 0 && i < state.quiz.questions.length) {
                state.quiz.questions[i] = question;
            }
        }
    } catch (e) {
        console.error("Failed to load quiz edits:", e);
    }
}
