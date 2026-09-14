import { setStoredQuestionIndex } from "../persistence/progress.js";
import { formatTime } from "../shared/formatting.js";
import { renderMarkdown } from "../shared/markdown.js";
import { UNANSWERED, WRONG, CORRECT, SKIPPED, state } from "../state.js";
import { saveTimer, updateTimer } from "../timer.js";
import { renderQuiz } from "./mcq.js";

export async function renderResults() {
    const questionBox = document.querySelector(".question-box");
    const results = document.getElementById("results");

    questionBox.style.display = "none";
    results.style.display = "";

    const correct = state.questionResults.filter((x) => x === CORRECT).length;
    const wrong = state.questionResults.filter((x) => x === WRONG).length;
    const unanswered = state.questionResults.filter((x) => x === UNANSWERED).length;
    const skipped = state.questionResults.filter((x) => x === SKIPPED).length;

    const total = state.quiz.questions.length;
    const answered = correct + wrong;

    const accuracy = answered > 0 ? (correct / answered) * 100 : 0;

    const elapsed = state.timer.visible
        ? state.timer.elapsed + Math.floor((Date.now() - state.timer.start) / 1000)
        : Math.floor((Date.now() - state.defaultStartDate) / 1000);

    const chartData = {
        labels: ["Correct", "Wrong", "Unanswered", "Skipped"],
        datasets: [
            {
                label: "Score Chart",
                data: [correct, wrong, unanswered, skipped],
                classNames: [
                    "chart-correct",
                    "chart-wrong",
                    "chart-unanswered",
                    "chart-skipped",
                ],
            },
        ],
    };
    document.getElementById("score").textContent =
        `Score: ${correct}/${wrong + correct}`;

    document.getElementById("accuracy").textContent =
        `Accuracy: ${accuracy.toFixed(1)}%`;

    document.getElementById("correct").textContent = `Correct: ${correct}`;

    document.getElementById("wrong").textContent = `Wrong: ${wrong}`;

    document.getElementById("unanswered").textContent =
        `Unanswered: ${unanswered}`;

    document.getElementById("skipped").textContent = `Skipped: ${skipped}`;

    document.getElementById("time").textContent =
        `Time: ${formatTime(elapsed)}`;

    document.getElementById("averageTime").textContent =
        `Average time per question: ${formatTime(Math.floor(elapsed / total))}`;

    createDonutChart(document.getElementById("statsChart"), chartData);
    showCorrectionSheet();

    if (state.mathReady && window.MathJax) {
        try {
            await MathJax.typesetPromise([
                document.getElementById("question-corrections"),
            ]);
        } catch (err) {
            console.error("MathJax typesetting failed:", err);
        }
    }
}

function createDonutChart(container, data) {
    const viewSize = 100;
    const center = viewSize / 2;

    const outerRadius = 37.5;
    const innerRadius = 20;
    const midRadius = (outerRadius + innerRadius) / 2;
    const strokeWidth = outerRadius - innerRadius;

    const circumference = 2 * Math.PI * midRadius;

    const values = data.datasets[0].data;
    const classNames = data.datasets[0].classNames;
    const total = values.reduce((sum, v) => sum + v, 0);

    let offset = 0;

    const arcs = values
        .map((value, i) => {
            if (value === 0 || total === 0) return "";

            const fraction = value / total;
            const dash = fraction * circumference;
            const gap = circumference - dash;

            const circle = `<circle
class="${classNames[i]}"
cx="${center}" cy="${center}" r="${midRadius}"
fill="none"
stroke-width="${strokeWidth}"
stroke-dasharray="${dash} ${gap}"
stroke-dashoffset="${-offset}"
transform="rotate(-90 ${center} ${center})"
/>`;

            offset += dash;
            return circle;
        })
        .join("");

    container.innerHTML = `
<svg viewBox="0 0 ${viewSize} ${viewSize}" preserveAspectRatio="xMidYMid meet" style="width: 100%; height: 100%; display: block;">
    ${arcs}
</svg>
`;
}


function showCorrectionSheet() {
    const container = document.getElementById("question-corrections");
    const questions = state.quiz.questions;

    container.innerHTML = "";

    for (let index = 0; index < questions.length; index++) {
        const question = questions[index];

        const correctAnswer = question.options[question.correct_index];

        const userIndex = state.questionAnswers[index];

        const userAnswer =
            state.questionResults[index] === SKIPPED
                ? "Skipped"
                : userIndex !== null
                    ? question.options[userIndex]
                    : "Unanswered";

        const article = document.createElement("article");

        article.innerHTML = `
<h3>Question ${index + 1}</h3>

<p>${renderMarkdown(question.question, state.mathReady)}</p>

<p>
    <strong>Your answer:</strong>
    ${renderMarkdown(userAnswer, state.mathReady)}
</p>

<p>
    <strong>Correct answer:</strong>
    ${renderMarkdown(correctAnswer, state.mathReady)}
</p>

${question.explanation
                ? `
<p>
    <strong>Explanation:</strong>
    ${renderMarkdown(question.explanation, state.mathReady)}
</p>
`
                : ""
            }
`;

        container.appendChild(article);
    }
}



const questionNumber = document.getElementById("question-number");

export function restartQuiz() {
    // Reset question state
    state.currentQuestionIndex = 0;
    questionNumber.value = 1;
    state.answerRevealed = false;
    state.wrongAnswerCount = 0;

    // Reset stats
    state.questionResults = new Array(state.quiz.questions.length).fill(UNANSWERED);
    state.questionAnswers = new Array(state.quiz.questions.length).fill(null);
    document.getElementById("question-corrections").innerHTML = "";

    // Reset timer
    clearInterval(state.timer.interval);
    state.timer.interval = null;

    state.timer.elapsed = 0;
    state.timer.start = state.timer.visible ? Date.now() : null;
    state.defaultStartDate = Date.now();

    const timerElement = document.getElementById("timer");
    if (state.timer.visible) {
        updateTimer();
        state.timer.interval = setInterval(updateTimer, 1000);
    } else {
        timerElement.textContent = formatTime(0);
    }
    saveTimer();

    // Reset stored question
    setStoredQuestionIndex(state.quizStorageKey, 0)

    // Return to quiz
    const results = document.getElementById("results");
    const questionBox = document.querySelector(".question-box");

    results.style.display = "none";
    questionBox.style.display = "";

    document.getElementById("restart-confirm").style.display = "none";

    renderQuiz();
}
