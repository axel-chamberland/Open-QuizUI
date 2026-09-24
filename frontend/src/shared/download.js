import { state } from "../state.js";

// Download the original HTML with the current app data.
export function downloadQuizHTML() {
  // quiz is the current runtime-modified quiz
  const appData = {
    mode: state.mode,
    enableMathJax: state.mathReady,
    quiz: state.quiz,
  };

  const filename = state.quiz.title;

  // Clone the document so the live page is not modified.
  const documentClone = document.documentElement.cloneNode(true);

  const questionScroll = documentClone.querySelector("#question-scroll");

  // Empty current quiz
  if (questionScroll) {
    questionScroll.querySelector("#question")?.replaceChildren();
    questionScroll.querySelector("#options")?.replaceChildren();
    questionScroll.querySelector("#explanation")?.replaceChildren();
  }

  // Reset flashcard-rendered content.
  const flashcardBox = documentClone.querySelector("#flashcard-box");

  if (flashcardBox) {
    flashcardBox.querySelector(".flashcard-question")?.replaceChildren();
    flashcardBox.querySelector(".flashcard-answer")?.replaceChildren();
    flashcardBox.querySelector(".flashcard-explanation")?.replaceChildren();
  }

  // Reset Dropdown menus
  documentClone.querySelectorAll(".dropdown-menu").forEach((menu) => {
    menu.classList.remove("show");
    menu.style.removeProperty("left");
    menu.style.removeProperty("top");
    menu.style.removeProperty("bottom");
  });

  // Replace the JSON payload in the cloned document.
  const dataScript = documentClone.querySelector("#app-data");

  if (!dataScript) {
    throw new Error("Could not find #app-data");
  }

  dataScript.textContent = JSON.stringify(appData, null, 2);

  // Serialize the cloned document.
  const html = "<!DOCTYPE html>\n" + documentClone.outerHTML;

  const blob = new Blob([html], { type: "text/html" });
  const url = URL.createObjectURL(blob);

  const a = document.createElement("a");
  a.href = url;
  a.download = filename.endsWith(".html") ? filename : filename + ".html";

  document.body.appendChild(a);
  a.click();
  a.remove();

  URL.revokeObjectURL(url);
}
