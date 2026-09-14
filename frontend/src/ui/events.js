import { goTo, nextQuestion, prevQuestion, handleAnswer, revealAnswer, } from "../quiz.js";
import { downloadQuizHTML } from "../shared/download.js";
import { state } from "../state.js";
import { toggleTimer } from "../timer.js";
import { copyQuiz, copyQuestion } from "../shared/clipboard.js";
import { closeEditorConfirm, openEditor, saveEdit } from "../rendering/editor.js";
import { confirmRestart, cancelRestart } from "../rendering/editor.js";
import { toggleFullscreen } from "./fullscreen.js";
import { restartQuiz } from "../rendering/results.js";

export function initializeEvents() {

    // Quiz page
    document.getElementById("prev-button")
        .addEventListener("click", prevQuestion);


    document.getElementById("next-button")
        .addEventListener("click", nextQuestion);

    document.getElementById("reveal-button")
        .addEventListener("click", revealAnswer);

    document.getElementById("maximize-button")
        .addEventListener("click", toggleFullscreen);


    document.getElementById("download-button")
        .addEventListener("click", downloadQuizHTML);

    document.getElementById("timer-toggle")
        .addEventListener("click", toggleTimer);

    document.getElementById("copy-all-button")
        .addEventListener("click", copyQuiz);

    document.getElementById("copy-question-button")
        .addEventListener("click", copyQuestion);


    document.getElementById("editor-button")
        .addEventListener("click", openEditor);


    // Results page

    document.getElementById("results-back-button")
        .addEventListener("click", prevQuestion);


    document.getElementById("results-maximize-button")
        .addEventListener("click", toggleFullscreen);



    document.getElementById("results-download-button")
        .addEventListener("click", downloadQuizHTML);


    document.getElementById("results-copy-all-button")
        .addEventListener("click", copyQuiz);


    document.getElementById("restart-button")
        .addEventListener("click", confirmRestart);


    document.getElementById("confirm-restart-button")
        .addEventListener("click", restartQuiz);


    document.getElementById("cancel-restart-button")
        .addEventListener("click", cancelRestart);


    // Editor


    document.getElementById("editor-save-button")
        .addEventListener("click", saveEdit);


    document.getElementById("editor-copy-button")
        .addEventListener("click", copyQuestion);


    document.getElementById("editor-maximize-button")
        .addEventListener("click", toggleFullscreen);


    document.getElementById("editor-close-button")
        .addEventListener("click", closeEditorConfirm);


    // Keybinds

    document.addEventListener("keydown", (e) => {
        if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;

        const key = e.key.toLowerCase();

        // Number = choose
        let index = -1;

        if (/^[1-9]$/.test(key)) {
            index = Number(key) - 1;
        }

        if (index >= 0 && index < state.optionButtons.length) {
            const button = state.optionButtons[index];
            if (!button.disabled) {
                handleAnswer(index, button);
            }
            return;
        }

        // Reveal answer or go to next question
        if (key === "enter" || key == " ") {
            e.preventDefault();

            if (!state.answerRevealed) {
                revealAnswer();
            } else {
                nextQuestion();
            }
            return;
        }

        // Navigation
        if (key === "arrowright" || key === "l") {
            e.preventDefault();
            nextQuestion();
            return;
        }

        if (key === "arrowleft" || key === "h") {
            e.preventDefault();
            prevQuestion();
            return;
        }
    });

    // Tap or click to change question (touch control)

    const questionBox = document.querySelector(".question-box");

    questionBox.addEventListener("click", (e) => {
        if (e.target.closest("button, input")) return;

        // Don't navigate if the user just made a text selection
        const selection = window.getSelection();
        if (selection && selection.toString().length > 0) return;

        const rect = questionBox.getBoundingClientRect();
        const x = e.clientX - rect.left;
        if (x > rect.width * 0.7) {
            if (!state.answerRevealed) {
                revealAnswer();
            } else {
                nextQuestion();
            }
        } else if (x < rect.width * 0.3) {
            prevQuestion();
        }
    });


    // Change question directly

    const questionSelector = document.getElementById("question-selector");
    const questionNumber = document.getElementById("question-number");

    questionSelector.addEventListener("click", () => {
        questionNumber.focus();
        questionNumber.select();
    });

    questionNumber.addEventListener("input", () => {
        questionNumber.value = questionNumber.value.replace(/\D/g, "");
    });
    questionNumber.addEventListener("change", () => {
        if (!questionNumber.value) return;

        goTo(Number(questionNumber.value) - 1);
    });


}
