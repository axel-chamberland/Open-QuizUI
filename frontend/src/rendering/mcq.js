import { state } from "../state.js";
import { renderMarkdown } from "../shared/markdown.js";
import { handleAnswer, renderQuestion, updateNavigation } from "../quiz.js";
import { typesetMath } from "../shared/mathjax.js";

export function showExplanation(question) {
  const explanationEl = document.getElementById("explanation");

  if (question.explanation) {
    explanationEl.innerHTML = renderMarkdown(
      question.explanation,
      state.mathReady,
    );
    explanationEl.style.display = "block";

    if (state.mathReady) {
      window.MathJax.typesetPromise([explanationEl]).catch((err) =>
        console.error("MathJax typesetting failed:", err),
      );
    }
  } else {
    explanationEl.innerHTML = "";
    explanationEl.style.display = "none";
  }
}

export async function renderQuiz() {
  const questionBox = document.getElementById("question-box");
  const questionText = questionBox.querySelector("#question");
  const optionsContainer = document.getElementById("options");
  const navigationContainer = questionBox.querySelector("#navigation");
  const explanationEl = document.getElementById("explanation");

  if (!state.quiz.questions || state.quiz.questions.length === 0) {
    document.getElementById("question").textContent =
      "No valid questions parsed";
    return;
  }

  // Update question
  const question = state.quiz.questions[state.currentQuestionIndex];
  state.currentQuestion = question;

  renderQuestion(questionText, question);

  // Clear explanation
  explanationEl.textContent = "";
  explanationEl.style.display = "none";

  // Clear and rebuild options
  renderOptions(optionsContainer, question);

  // Update button states
  updateNavigation();

  document.getElementById("question-scroll").scrollTop = 0; // reset scroll

  await typesetMath();
}
function renderOptions(optionsContainer, question) {
  optionsContainer.innerHTML = "";
  // Answer button is revealed when user exhausted all options
  state.wrongAnswerCount = 0;
  state.optionButtons = [];

  question.options.forEach((option, index) => {
    const button = document.createElement("button");

    button.innerHTML = renderMarkdown(option, state.mathReady);
    button.className = "option";

    state.optionButtons.push(button);

    button.addEventListener("click", () => {
      handleAnswer(index, button);
    });

    optionsContainer.appendChild(button);
  });
}
