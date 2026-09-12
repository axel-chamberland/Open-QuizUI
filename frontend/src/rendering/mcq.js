import { state } from "../state.js";
import { renderMarkdown } from "../shared/markdown.js";
import { handleAnswer } from "../quiz.js";

export function showExplanation(question) {
    const explanationEl = document.getElementById("explanation");

    if (question.explanation) {
        explanationEl.innerHTML = renderMarkdown(question.explanation, state.mathReady);
        explanationEl.style.display = "block";


        if (state.mathReady && window.MathJax) {
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
    const questionBox = document.querySelector(".question-box");
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
    questionText.innerHTML = renderMarkdown(
        state.quiz.questions[state.currentQuestionIndex].question, state.mathReady
    );

    // Clear explanation
    explanationEl.textContent = "";
    explanationEl.style.display = "none";

    // Clear and rebuild options
    optionsContainer.innerHTML = "";
    state.wrongAnswerCount = 0; // Answer button is revealed when user exhausted all options
    state.optionButtons = [];

    state.currentQuestion = state.quiz.questions[state.currentQuestionIndex];
    state.currentQuestion.options.forEach((option, index) => {
        const button = document.createElement("button");
        button.innerHTML = renderMarkdown(option, state.mathReady);
        button.className = "option";

        state.optionButtons.push(button);

        button.addEventListener("click", () => {
            handleAnswer(index, button);
        });

        optionsContainer.appendChild(button);
    });
    // Update button states
    const prevButton = navigationContainer.querySelector("#prev-button");
    prevButton.disabled = state.currentQuestionIndex === 0;

    // Next button is not disabled as it goes to the result screen after last question

    document.getElementById("question-scroll").scrollTop = 0; // reset scroll

    if (state.mathReady && window.MathJax) {
        try {
            await window.MathJax.typesetPromise();
        } catch (err) {
            console.error("MathJax typesetting failed:", err);
        }
    }
}

