import { state } from "../state.js";
import { formatQuizAsText } from "./formatting.js";

export async function copyQuestion() {
  const question = state.quiz.questions[state.currentQuestionIndex];

  const quiz = {
    title: state.quiz.title,
    questions: [question],
  };

  await copyToClipboard(formatQuizAsText(quiz));
}

// TODO: add new order for using questionOrder
// instead of default quiz order (future proof for when adding
// and moving questions is supported).
export async function copyQuiz() {
  await copyToClipboard(formatQuizAsText(state.quiz));
}

async function copyToClipboard(text) {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (error) {
      console.warn("Clipboard API failed, trying fallback:", error);
    }
  }

  return copyToClipboardFallback(text);
}

function copyToClipboardFallback(text) {
  const textarea = document.createElement("textarea");

  textarea.value = text;
  textarea.style.position = "fixed";
  textarea.style.left = "-9999px";
  textarea.style.top = "0";
  textarea.setAttribute("readonly", "");

  document.body.appendChild(textarea);

  textarea.select();
  textarea.setSelectionRange(0, textarea.value.length);

  let success = false;

  try {
    success = document.execCommand("copy");
  } catch (error) {
    console.error("Fallback copy failed:", error);
  }

  document.body.removeChild(textarea);

  return success;
}
