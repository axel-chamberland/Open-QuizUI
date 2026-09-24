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
import { restoreQuizToDefault } from "../rendering/editor.js";
import { toggleFullscreen } from "./fullscreen.js";
import {
  cancelRestart,
  confirmRestart,
  restartQuiz,
} from "../rendering/results.js";
import { rateFlashcard } from "../rendering/flashcards.js";

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

  document
    .querySelector(".known-button")
    .addEventListener("click", () => rateFlashcard(true));

  document
    .querySelector(".unknown-button")
    .addEventListener("click", () => rateFlashcard(false));

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

  // TODO: Change to alert system
  document
    .getElementById("editor-close-button")
    .addEventListener("click", closeEditorConfirm);

  document
    .getElementById("reset-quiz-button")
    .addEventListener("click", restoreQuizToDefault);

  document
    .getElementById("reset-question-button")
    .addEventListener("click", restoreQuestionToDefault);

  // Drop down menus
  document.querySelectorAll(".dropdown-trigger").forEach((trigger) => {
    const menuId = trigger.id.replace("-menu-button", "-dropdown-menu");
    const menu = document.getElementById(menuId);
    const navigation = trigger.closest(".navigation");
    const navigationScroll = navigation.parentElement;

    const positionMenu = () => {
      if (!menu.classList.contains("show")) return;

      const rect = trigger.getBoundingClientRect();
      const navRect = navigationScroll.getBoundingClientRect();

      // Clamp to page width
      menu.style.left = `${Math.min(
        rect.right,
        navRect.right - menu.offsetWidth,
      )}px`;

      // Orientation is different in fullscreen
      if (
        document.fullscreenElement ||
        document.documentElement.classList.contains("pseudo-fullscreen-active")
      ) {
        // Orient up
        menu.style.top = "auto";
        menu.style.bottom = `${
          document.documentElement.clientHeight - navRect.top
        }px`;
      } else {
        // Orient down, below navbar
        menu.style.top = `${rect.bottom}px`;
        menu.style.bottom = "auto";
      }
    };

    trigger.addEventListener("click", (e) => {
      e.stopPropagation();

      menu.classList.toggle("show");
      positionMenu();
    });

    // Re-position on window resize
    const observer = new ResizeObserver(positionMenu);
    observer.observe(navigation);
    window.addEventListener("scroll", positionMenu, true);

    menu.querySelectorAll("button").forEach((button) => {
      button.addEventListener("click", () => {
        menu.classList.remove("show");
      });
    });

    document.addEventListener("click", (e) => {
      if (!e.target.closest(".dropdown-trigger, .dropdown-menu")) {
        document.querySelectorAll(".dropdown-menu.show").forEach((menu) => {
          menu.classList.remove("show");
        });
      }
    });
  });

  // Quiz Keybinds

  document.addEventListener("keydown", (e) => {
    if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;

    if (
      document.getElementById("question-box")?.style.display === "none" &&
      document.getElementById("flashcard-box")?.style.display === "none"
    ) {
      return;
    }

    const key = e.key.toLowerCase();

    // Flashcard rating
    if (state.mode === "flashcard") {
      if (key === "1") {
        rateFlashcard(false); // ✗ unknown
        return;
      }

      if (key === "2") {
        rateFlashcard(true); // ✓ known
        return;
      }
    }

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
      } else if (state.mode === "flashcard") {
        rateFlashcard(true);
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
