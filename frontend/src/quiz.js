import { renderQuiz, showExplanation } from "./rendering/mcq.js"
import { saveStats } from "./persistence/stats.js";
import { renderResults } from "./rendering/results.js";
import { UNANSWERED, WRONG, CORRECT, SKIPPED, state } from "./state.js";
import { setStoredQuestionIndex } from "./persistence/progress.js";

const results = document.getElementById("results");


export function nextQuestion() {
    if (
        state.currentQuestionIndex >= state.quiz.questions.length - 1 &&
        results.style.display === "none"
    ) {
        renderResults();
        return;
    }
    goTo(state.currentQuestionIndex + 1);
}

export function prevQuestion() {
    const results = document.getElementById("results");

    if (results.style.display !== "none") {
        results.style.display = "none";
        document.querySelector(".question-box").style.display = "";
        renderQuiz();
        return;
    }

    if (state.currentQuestionIndex <= 0) return;
    goTo(state.currentQuestionIndex - 1);
}


export function goTo(question_index) {
    // Clamp between first and last question
    question_index = Math.max(
        0,
        Math.min(question_index, state.quiz.questions.length - 1),
    );

    state.currentQuestionIndex = question_index;

    setStoredQuestionIndex(state.quizStorageKey, state.currentQuestionIndex);

    state.answerRevealed = false;


    const questionNumber = document.getElementById("question-number");
    questionNumber.value = state.currentQuestionIndex + 1;
    renderQuiz();
}

export function handleAnswer(index, button) {
    saveStats();
    if (index === state.currentQuestion.correct_index) {
        button.classList.add("correct");
        button.disabled = true;
        state.answerRevealed = true;
        if (state.wrongAnswerCount === 0) {
            state.questionResults[state.currentQuestionIndex] = CORRECT;
            state.questionAnswers[state.currentQuestionIndex] = index;
            saveStats();
        }
        state.optionButtons.forEach((btn) => (btn.disabled = true));
        showExplanation(state.currentQuestion);
    } else {
        button.classList.add("wrong");
        button.disabled = true;
        state.questionResults[state.currentQuestionIndex] = WRONG;

        if (state.questionAnswers[state.currentQuestionIndex] === null) {
            state.questionAnswers[state.currentQuestionIndex] = index;
        }
        saveStats();
        state.wrongAnswerCount++;
        if (state.wrongAnswerCount === state.currentQuestion.options.length - 1) {
            revealAnswer();
        }
    }
}

export function revealAnswer() {
    state.answerRevealed = true;
    if (state.questionResults[state.currentQuestionIndex] === UNANSWERED) {
        state.questionResults[state.currentQuestionIndex] = SKIPPED;
        saveStats();
    }
    state.currentQuestion = state.quiz.questions[state.currentQuestionIndex];
    const optionsContainer = document.getElementById("options");
    // Get all buttons in the current question
    const buttons = optionsContainer.querySelectorAll("button");
    // Highlight the correct answer
    buttons[state.currentQuestion.correct_index].classList.add("correct");
    showExplanation(state.currentQuestion);
}


export function setQuizTitle(title) {
    const displayTitle = title.slice(0, 60);

    document.title = displayTitle;
    document.getElementById("title").textContent = title;
}
