import { state } from "../state.js";
import { formatQuizAsText } from "./formatting.js";


export async function copyQuestion() {
    const question = state.quiz.questions[state.currentQuestionIndex];

    const quiz = {
        title: state.quiz.title,
        questions: [question],
    };

    await copyToClipboard(
        formatQuizAsText(
            quiz,
        ),
    );
}

export async function copyQuiz() {
    await copyToClipboard(
        formatQuizAsText(
            state.quiz,
        ),
    );
}

async function copyToClipboard(text) {
    if (navigator.clipboard?.writeText) {
        try {
            await navigator.clipboard.writeText(text);
            return true;
        } catch (error) {
            console.error("Failed to copy:", error);
        }
    }

    return false;
}
