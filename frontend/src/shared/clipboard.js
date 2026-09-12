import { state } from "../state.js";
import { formatQuizAsText, formatQuestionAsText, formatAnswerKey } from "./formatting.js";


export function copyQuestion() {
    const question = state.quiz.questions[state.currentQuestionIndex];

    const text = [
        formatQuestionAsText(question, state.currentQuestionIndex),
        "",
        formatAnswerKey([question]),
    ].join("\n");

    copyToClipboard(text, "Question copied to clipboard.");
}

export function copyQuiz() {
    copyToClipboard(formatQuizAsText(state.quiz), "Quiz copied to clipboard.");
}

async function copyToClipboard(text) {
    if (navigator.clipboard?.writeText) {
        try {
            await navigator.clipboard.writeText(text);
            return true;
        } catch { }
    }

    return false;
}


