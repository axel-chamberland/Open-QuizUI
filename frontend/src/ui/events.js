import {
  goTo,
  nextQuestion,
  prevQuestion,
  handleAnswer,
  revealAnswer,
  switchMode,
} from "../quiz.js";
import { downloadQuizHTML } from "../shared/download.js";
import { state } from "../state.js";
import { toggleTimer } from "../timer.js";
import { copyQuiz, copyQuestion } from "../shared/clipboard.js";
import {
  closeEditorConfirm,
  openEditor,
  restoreQuestionToDefault,
  saveEdit,
} from "../rendering/editor.js";
import {
  confirmRestart,
  cancelRestart,
  restoreQuizToDefault,
} from "../rendering/editor.js";
import { toggleFullscreen } from "./fullscreen.js";
import { restartQuiz } from "../rendering/results.js";

export function initializeEvents() {
  // Quiz page

  document.querySelectorAll(".reveal-button").forEach((button) => {
    button.addEventListener("click", revealAnswer);
  });

  document.querySelectorAll(".timer-toggle-button").forEach((button) => {
    button.addEventListener("click", toggleTimer);
  });

  document.querySelectorAll(".prev-button").forEach((button) => {
    button.addEventListener("click", prevQuestion);
  });

  document.querySelectorAll(".next-button").forEach((button) => {
    button.addEventListener("click", nextQuestion);
  });
  document.querySelectorAll(".download-button").forEach((button) => {
    button.addEventListener("click", downloadQuizHTML);
  });
  document.querySelectorAll(".maximize-button").forEach((button) => {
    button.addEventListener("click", toggleFullscreen);
  });

  document.querySelectorAll(".copy-all-button").forEach((button) => {
    button.addEventListener("click", copyQuiz);
  });

  document.querySelectorAll(".copy-question-button").forEach((button) => {
    button.addEventListener("click", copyQuestion);
  });

  document.querySelectorAll(".editor-button").forEach((button) => {
    button.addEventListener("click", openEditor);
  });

  document.querySelectorAll(".mode-button").forEach((button) => {
    button.addEventListener("click", switchMode);
  });

  // Results page

  document
    .getElementById("results-back-button")
    .addEventListener("click", prevQuestion);

  document
    .getElementById("restart-button")
    .addEventListener("click", confirmRestart);

  document
    .getElementById("confirm-restart-button")
    .addEventListener("click", restartQuiz);

  document
    .getElementById("cancel-restart-button")
    .addEventListener("click", cancelRestart);

  // Editor

  document
    .getElementById("editor-save-button")
    .addEventListener("click", saveEdit);

  document
    .getElementById("editor-close-button")
    .addEventListener("click", closeEditorConfirm);

  document
    .getElementById("reset-quiz-button")
    .addEventListener("click", restoreQuizToDefault);

  document
    .getElementById("reset-question-button")
    .addEventListener("click", restoreQuestionToDefault);

  // Drop down menu
  const trigger = document.getElementById("actions-button");
  const menu = document.getElementById("dropdown-menu");

  trigger.addEventListener("click", (e) => {
    e.stopPropagation();
    menu.classList.toggle("show");
  });

  document.addEventListener("click", (e) => {
    if (!menu.contains(e.target) && !trigger.contains(e.target)) {
      menu.classList.remove("show");
    }
  });

  // Keybinds

  document.addEventListener("keydown", (e) => {
    if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;

    const key = e.key.toLowerCase();

    // Number = choose
    let index = -1;

    if (/^[1-9]$/.test(key)) {
      index = Number(key) - 1;
    }

    if (
      index >= 0 &&
      index < state.optionButtons.length &&
      state.mode == "mcq"
    ) {
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

  const questionBox = document.getElementById("question-box");

  const flashcardBox = document.getElementById("flashcard-box");

  function handleBoxClick(e) {
    if (e.target.closest("button, input")) return;

    // Don't navigate if the user just made a text selection
    const selection = window.getSelection();
    if (selection && selection.toString().length > 0) return;

    const box = e.currentTarget;
    const rect = box.getBoundingClientRect();
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
  }

  questionBox.addEventListener("click", handleBoxClick);
  flashcardBox.addEventListener("click", handleBoxClick);
  // Change question directly

  document
    .querySelectorAll(".question-selector")
    .forEach((questionSelector) => {
      const questionNumber = questionSelector.querySelector(".question-number");

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
    });
}
