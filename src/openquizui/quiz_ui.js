const appData = JSON.parse(document.getElementById("app-data").textContent);

const ENABLE_MATHJAX = appData.enableMathJax;

const quiz = appData.quiz;

// Detect if in an iframe (used for better UI support)
if (window.self !== window.top) {
    document.body.classList.add("embedded");
}

let mathReady = false;

let wrongAnswerCount = 0;

let optionButtons = [];
let currentQuestion = null;

let answerRevealed = false;

// Timer
let timerVisible = false;
let timerStart = null;
let timerElapsed = 0;
let timerInterval = null;

// Key for local storage
const quizStorageKey = hashQuiz(quiz);

// Stats
const UNANSWERED = 0;
const CORRECT = 1;
const WRONG = 2;
const SKIPPED = 3;
let questionResults = new Array(quiz.questions.length).fill(UNANSWERED);
let questionAnswers = new Array(quiz.questions.length).fill(null);
let defaultStartDate = Date.now(); // Default start date used if timer was never started
loadStats();

// Question editing
loadQuizEdits();

const timer = document.getElementById("timer");
const questionBox = document.querySelector(".question-box");
const questionText = questionBox.querySelector("#question");
const optionsContainer = document.getElementById("options");
const navigationContainer = questionBox.querySelector("#navigation");
const questionNumber = document.getElementById("question-number");
const results = document.getElementById("results");

// Update title
document.getElementById("title").textContent = quiz.title;

// Update max question count
const questionCount = document.getElementById("question-count");

questionCount.textContent = quiz.questions.length;

let currentQuestionIndex = getStoredQuestionIndex();
questionNumber.value = currentQuestionIndex + 1;

window.MathJax = {
    tex: {
        inlineMath: [
            ["$", "$"],
            ["\\(", "\\)"],
        ],
    },
};

function loadMathJax() {
    return new Promise((resolve) => {
        if (!ENABLE_MATHJAX) {
            mathReady = false;
            resolve(false);
            return;
        }

        const script = document.createElement("script");
        script.src =
            "https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js";

        script.onload = () => {
            mathReady = true;
            resolve(true);
        };

        script.onerror = () => {
            mathReady = false;
            resolve(false);
        };

        document.head.appendChild(script);
    });
}

// UI events

// In case the iframe was reset while in fullscreen, reload the page to reset affected elements
// This mainly happens when you call the action function on another device while being in pseudo-fullscreen,
// causing the iframe to reset without exiting pseudo-fullscreen
try {
    if (
        window.top.document.body.classList.contains("pseudo-fullscreen-active")
    ) {
        window.top.location.reload();
    }
} catch {
    // The iframe may not be permitted to access the top document
    // when origin restrictions are disabled.
    // This is fine, since it means that pseudo-fullscreen did not modify anything that needs to be reset
}

async function toggleFullscreen() {
    if (document.fullscreenElement || document.webkitFullscreenElement) {
        if (document.exitFullscreen) await document.exitFullscreen();
        else document.webkitExitFullscreen?.();
        return;
    }
    if (
        document.documentElement.classList.contains("pseudo-fullscreen-active")
    ) {
        document.documentElement.classList.remove("pseudo-fullscreen-active");
        exitPseudoFullscreen();
        return;
    }
    const root = document.documentElement;
    if (root.requestFullscreen) {
        try {
            await root.requestFullscreen();
            return;
        } catch {}
    } else if (root.webkitRequestFullscreen) {
        root.webkitRequestFullscreen();
        return;
    }

    // support for navigators that don't support fullscreen in iframes, such as iOS webkit (thanks, Apple!)
    document.documentElement.classList.add("pseudo-fullscreen-active");
    enterPseudoFullscreen();
}

let pseudoFullscreenState = null;

function enterPseudoFullscreen() {
    const iframe = window.frameElement;

    // Keep track of fullscreen state in case the iframe is reset while in fullscreen (force a page reload)
    const topBody = window.top.document.body;
    topBody.classList.add("pseudo-fullscreen-active");

    pseudoFullscreenState = {
        scrollX: window.top.scrollX,
        scrollY: window.top.scrollY,
        elements: [],
    };

    let el = iframe;

    while (el && el !== document.body) {
        pseudoFullscreenState.elements.push({
            el,
            style: el.getAttribute("style"),
            siblings: [...el.parentElement.children]
                .filter((x) => x !== el)
                .map((x) => [x, x.style.display]),
        });

        el.style.position = "fixed";
        el.style.inset = "0";
        el.style.width = "100vw";
        el.style.height = "100dvh";
        el.style.margin = "0";
        el.style.maxWidth = "none";
        el.style.maxHeight = "none";
        el.style.zIndex = "999999";

        for (const child of el.parentElement.children) {
            if (child !== el) child.style.display = "none";
        }

        el = el.parentElement;
    }
}

function exitPseudoFullscreen() {
    const topBody = window.top.document.body;

    topBody.classList.remove("pseudo-fullscreen-active");

    if (!pseudoFullscreenState) {
        return;
    }

    const { elements, scrollX, scrollY } = pseudoFullscreenState;

    for (const item of elements) {
        if (item.style === null) item.el.removeAttribute("style");
        else item.el.setAttribute("style", item.style);

        for (const [sibling, display] of item.siblings)
            sibling.style.display = display;
    }

    pseudoFullscreenState = null;

    // Return the top page to where it was.
    window.top.scrollTo(scrollX, scrollY);

    // Make sure the iframe itself is visible.
    window.frameElement.scrollIntoView({
        block: "center",
        inline: "nearest",
    });
}
document.addEventListener("keydown", (e) => {
    if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;

    const key = e.key.toLowerCase();

    // Number = choose
    let index = -1;

    if (/^[1-9]$/.test(key)) {
        index = Number(key) - 1;
    }

    if (index >= 0 && index < optionButtons.length) {
        const button = optionButtons[index];
        if (!button.disabled) {
            handleAnswer(index, button);
        }
        return;
    }

    // Reveal answer or go to next question
    if (key === "enter" || key == " ") {
        e.preventDefault();

        if (!answerRevealed) {
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

questionBox.addEventListener("click", (e) => {
    if (e.target.closest("button, input")) return;

    // Don't navigate if the user just made a text selection
    const selection = window.getSelection();
    if (selection && selection.toString().length > 0) return;

    const rect = questionBox.getBoundingClientRect();
    const x = e.clientX - rect.left;
    if (x > rect.width * 0.7) {
        if (!answerRevealed) {
            revealAnswer();
        } else {
            nextQuestion();
        }
    } else if (x < rect.width * 0.3) {
        prevQuestion();
    }
});

// Helpers

function renderMath(text) {
    if (!text) return "";

    return text.replace(/\$(.+?)\$/g, (match, expr) => {
        if (mathReady && window.MathJax) {
            return match;
        }
        return `<code>${expr}</code>`;
    });
}

function renderMarkdown(text) {
    if (!text) return "";

    const protectedParts = [];

    function protect(value) {
        const index = protectedParts.length;
        protectedParts.push(value);
        return `\uE000${index}\uE001`;
    }

    function escapeHtml(value) {
        return value
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    // Protect fenced code blocks first.
    // Everything inside a fenced block is treated literally.
    text = text.replace(/```(?:[^\n`]*)\n([\s\S]*?)```/g, (_, content) =>
        protect(`<pre><code>${escapeHtml(content)}</code></pre>`),
    );

    // Protect inline code.
    // Everything between backticks is treated literally.
    text = text.replace(/`([^`]*?)`/g, (_, content) =>
        protect(`<code>${escapeHtml(content)}</code>`),
    );

    // Protect math from Markdown processing.
    text = text.replace(/\$\$[\s\S]*?\$\$/g, protect);
    text = text.replace(/\$(?!\$)[\s\S]*?\$(?!\$)/g, protect);

    // Escape things that look like HTML tags but aren't actually
    // part of a valid HTML element.
    const voidElements = new Set([
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    ]);

    text = text.replace(
        /<\/?(\p{L}[\p{L}\p{N}-]*)(?:\s[^>]*)?>/gu,
        (match, tagName, offset, wholeText) => {
            const tag = tagName.toLowerCase();

            // Closing tags are valid if they appear.
            if (match.startsWith("</")) {
                return match;
            }

            // Self-closing tags are valid.
            if (/\/>$/.test(match)) {
                return match;
            }

            // Void HTML elements don't need a closing tag.
            if (voidElements.has(tag)) {
                return match;
            }

            // For normal elements, require a matching closing tag.
            const closingTag = new RegExp(`</${tag}\\s*>`, "iu");

            if (closingTag.test(wholeText.slice(offset + match.length))) {
                return match;
            }

            // Otherwise, treat it as literal text.
            return match.replace(/</g, "&lt;").replace(/>/g, "&gt;");
        },
    );

    // Markdown.
    // Code spans and code blocks are already protected.
    text = text
        .replace(/\*\*(.*?)\*\*/g, "<b>$1</b>")
        .replace(/\*(.*?)\*/g, "<i>$1</i>");

    // Restore protected content.
    text = text.replace(
        /\uE000(\d+)\uE001/g,
        (_, index) => protectedParts[Number(index)],
    );

    return renderMath(text);
}

async function renderQuiz() {
    const questionBox = document.querySelector(".question-box");
    const questionText = questionBox.querySelector("#question");
    const optionsContainer = document.getElementById("options");
    const navigationContainer = questionBox.querySelector("#navigation");
    const explanationEl = document.getElementById("explanation");

    if (!quiz.questions || quiz.questions.length === 0) {
        document.getElementById("question").textContent =
            "No valid questions parsed";
        return;
    }

    // Update question
    questionText.innerHTML = renderMarkdown(
        quiz.questions[currentQuestionIndex].question,
    );

    // Clear explanation
    explanationEl.textContent = "";
    explanationEl.style.display = "none";

    // Clear and rebuild options
    optionsContainer.innerHTML = "";
    wrongAnswerCount = 0; // Answer button is revealed when user exhausted all options
    optionButtons = [];

    currentQuestion = quiz.questions[currentQuestionIndex];
    currentQuestion.options.forEach((option, index) => {
        const button = document.createElement("button");
        button.innerHTML = renderMarkdown(option);
        button.className = "option";

        optionButtons.push(button);

        button.addEventListener("click", () => {
            handleAnswer(index, button);
        });

        optionsContainer.appendChild(button);
    });
    // Update button states
    const prevButton = navigationContainer.querySelector("#prev-button");
    prevButton.disabled = currentQuestionIndex === 0;

    // Next button is not disabled as it goes to the result screen after last question
    // const nextButton = navigationContainer.querySelector("#next-button");
    // nextButton.disabled = currentQuestionIndex === quiz.questions.length - 1;

    document.getElementById("question-scroll").scrollTop = 0; // reset scroll

    try {
        await MathJax.typesetPromise();
    } catch (err) {
        console.error("MathJax typesetting failed:", err);
    }
}

function nextQuestion() {
    if (
        currentQuestionIndex >= quiz.questions.length - 1 &&
        results.style.display === "none"
    ) {
        renderResults();
        return;
    }
    goTo(currentQuestionIndex + 1);
}

function prevQuestion() {
    const results = document.getElementById("results");

    if (results.style.display !== "none") {
        results.style.display = "none";
        document.querySelector(".question-box").style.display = "";
        renderQuiz();
        return;
    }

    if (currentQuestionIndex <= 0) return;
    goTo(currentQuestionIndex - 1);
}

// Change question directly
const questionSelector = document.getElementById("question-selector");

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

function goTo(question_index) {
    // Clamp between first and last question
    question_index = Math.max(
        0,
        Math.min(question_index, quiz.questions.length - 1),
    );

    currentQuestionIndex = question_index;

    setStoredQuestionIndex(currentQuestionIndex);

    answerRevealed = false;

    questionNumber.value = currentQuestionIndex + 1;
    renderQuiz();
}

function handleAnswer(index, button) {
    questionAnswers[currentQuestionIndex] = index;
    saveStats();
    if (index === currentQuestion.correct_index) {
        button.classList.add("correct");
        button.disabled = true;
        answerRevealed = true;
        if (wrongAnswerCount === 0) {
            questionResults[currentQuestionIndex] = CORRECT;
            saveStats();
        }
        optionButtons.forEach((btn) => (btn.disabled = true));
        showExplanation(currentQuestion);
    } else {
        button.classList.add("wrong");
        button.disabled = true;
        questionResults[currentQuestionIndex] = WRONG;
        saveStats();
        wrongAnswerCount++;
        if (wrongAnswerCount === currentQuestion.options.length - 1) {
            revealAnswer();
        }
    }
}

function revealAnswer() {
    answerRevealed = true;
    if (questionResults[currentQuestionIndex] === UNANSWERED) {
        questionResults[currentQuestionIndex] = SKIPPED;
        saveStats();
    }
    const currentQuestion = quiz.questions[currentQuestionIndex];
    const optionsContainer = document.getElementById("options");
    // Get all buttons in the current question
    const buttons = optionsContainer.querySelectorAll("button");
    // Highlight the correct answer
    buttons[currentQuestion.correct_index].classList.add("correct");
    showExplanation(currentQuestion);
}

function showExplanation(question) {
    const explanationEl = document.getElementById("explanation");

    if (question.explanation) {
        explanationEl.innerHTML = renderMarkdown(question.explanation);
        explanationEl.style.display = "block";

        if (mathReady && window.MathJax) {
            MathJax.typesetPromise([explanationEl]).catch((err) =>
                console.error("MathJax typesetting failed:", err),
            );
        }
    } else {
        explanationEl.innerHTML = "";
        explanationEl.style.display = "none";
    }
}

// Download as HTML.
function downloadQuizHTML(filename = quiz.title) {
    let html = "<!DOCTYPE html>\n" + document.documentElement.outerHTML;

    // Grab the existing JSON payload from the DOM
    const dataScript = document.getElementById("app-data");
    let appData = JSON.parse(dataScript.textContent);

    // Update the quiz property with current runtime edits
    appData.quiz = quiz;

    // Stringify the updated object safely
    const jsonPayload = JSON.stringify(appData, null, 2).replace(
        /</g,
        "\\u003c",
    );

    // Replace the content inside the JSON script tag
    html = html.replace(
        /(<script\s+id="app-data"\s+type="application\/json">)[\s\S]*?(<\/script>)/i,
        `$1\n${jsonPayload}\n$2`,
    );

    const blob = new Blob([html], { type: "text/html" });
    const url = URL.createObjectURL(blob);

    const a = document.createElement("a");
    a.href = url;
    a.download = filename.endsWith(".html") ? filename : filename + ".html";
    document.body.appendChild(a);
    a.click();

    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// Timer

function getTimerKey() {
    return `quizTimer_${quizStorageKey}`;
}

function loadTimer() {
    try {
        const data = JSON.parse(localStorage.getItem(getTimerKey()));

        timerElapsed = data?.elapsed || 0;
        timerStart = data?.start || null;
    } catch {
        timerElapsed = 0;
        timerStart = null;
    }
}

function saveTimer() {
    try {
        localStorage.setItem(
            getTimerKey(),
            JSON.stringify({
                elapsed: timerElapsed,
                start: timerStart,
            }),
        );
    } catch {}
}

function updateTimer() {
    if (!timerStart) return;

    const elapsed = timerElapsed + Math.floor((Date.now() - timerStart) / 1000);

    timer.textContent = formatTime(elapsed);
}

function toggleTimer() {
    timerVisible = !timerVisible;
    timer.classList.toggle("visible", timerVisible);

    if (timerVisible) {
        loadTimer();

        // Start
        if (!timerStart) {
            timerStart = Date.now();
            saveTimer();
        }

        updateTimer();
        timerInterval = setInterval(updateTimer, 1000);
    } else {
        // Pause
        if (timerStart) {
            timerElapsed += Math.floor((Date.now() - timerStart) / 1000);

            timerStart = null;
            saveTimer();
        }

        clearInterval(timerInterval);
        timerInterval = null;
    }
}

// Render results page

async function renderResults() {
    const questionBox = document.querySelector(".question-box");
    const results = document.getElementById("results");

    questionBox.style.display = "none";
    results.style.display = "";

    const correct = questionResults.filter((x) => x === CORRECT).length;
    const wrong = questionResults.filter((x) => x === WRONG).length;
    const unanswered = questionResults.filter((x) => x === UNANSWERED).length;
    const skipped = questionResults.filter((x) => x === SKIPPED).length;

    const total = quiz.questions.length;
    const answered = correct + wrong;

    const accuracy = answered > 0 ? (correct / answered) * 100 : 0;

    const elapsed = timerVisible
        ? timerElapsed + Math.floor((Date.now() - timerStart) / 1000)
        : Math.floor((Date.now() - defaultStartDate) / 1000);

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

    if (mathReady && window.MathJax) {
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

function formatTime(seconds) {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;

    return `${String(minutes).padStart(2, "0")}:${String(remainingSeconds).padStart(2, "0")}`;
}

function getStatsKey() {
    return `quizStats_${quizStorageKey}`;
}

function loadStats() {
    try {
        const data = JSON.parse(localStorage.getItem(getStatsKey()));

        if (Array.isArray(data?.results)) {
            questionResults = data.results;
        }

        if (Array.isArray(data?.answers)) {
            questionAnswers = data.answers;
        }

        if (data?.startDate) {
            defaultStartDate = data.startDate;
        }
    } catch {
        questionResults = new Array(quiz.questions.length).fill(UNANSWERED);
        questionAnswers = new Array(quiz.questions.length).fill(null);
        defaultStartDate = Date.now();
    }
}

function saveStats() {
    try {
        localStorage.setItem(
            getStatsKey(),
            JSON.stringify({
                results: questionResults,
                answers: questionAnswers,
                startDate: defaultStartDate,
            }),
        );
    } catch {}
}

function restartQuiz() {
    // Reset question state
    currentQuestionIndex = 0;
    questionNumber.value = 1;
    answerRevealed = false;
    wrongAnswerCount = 0;

    // Reset stats
    questionResults = new Array(quiz.questions.length).fill(UNANSWERED);
    questionAnswers = new Array(quiz.questions.length).fill(null);
    document.getElementById("question-corrections").innerHTML = "";

    // Reset timer
    clearInterval(timerInterval);
    timerInterval = null;

    timerElapsed = 0;
    timerStart = timerVisible ? Date.now() : null;
    defaultStartDate = Date.now();

    if (timerVisible) {
        updateTimer();
        timerInterval = setInterval(updateTimer, 1000);
    } else {
        timer.textContent = formatTime(0);
    }
    saveTimer();

    // Reset stored question
    setStoredQuestionIndex(0);

    // Return to quiz
    results.style.display = "none";
    questionBox.style.display = "";

    document.getElementById("restart-confirm").style.display = "none";

    renderQuiz();
}

function confirmRestart() {
    document.getElementById("restart-confirm").style.display = "flex";
}

function cancelRestart() {
    document.getElementById("restart-confirm").style.display = "none";
}

function showCorrectionSheet() {
    const container = document.getElementById("question-corrections");
    const questions = quiz.questions;

    container.innerHTML = "";

    for (let index = 0; index < questions.length; index++) {
        const question = questions[index];

        const correctAnswer = question.options[question.correct_index];

        const userIndex = questionAnswers[index];

        const userAnswer =
            questionResults[index] === SKIPPED
                ? "Skipped"
                : userIndex !== null
                  ? question.options[userIndex]
                  : "Unanswered";

        const article = document.createElement("article");

        article.innerHTML = `
<h3>Question ${index + 1}</h3>

<p>${renderMarkdown(question.question)}</p>

<p>
    <strong>Your answer:</strong>
    ${renderMarkdown(userAnswer)}
</p>

<p>
    <strong>Correct answer:</strong>
    ${renderMarkdown(correctAnswer)}
</p>

${
    question.explanation
        ? `
<p>
    <strong>Explanation:</strong>
    ${renderMarkdown(question.explanation)}
</p>
`
        : ""
}
`;

        container.appendChild(article);
    }
}

// Editor UI Functions

document
    .getElementById("editor-answer-number")
    .addEventListener("input", (e) => {
        e.target.value = e.target.value.replace(/\D/g, "");
    });

function openEditor() {
    const questionBox = document.querySelector(".question-box");
    const editor = document.getElementById("editor");
    const prompt = document.getElementById("editor-close");

    prompt.classList.remove("visible");

    questionBox.style.display = "none";
    editor.style.display = "";

    const titleField = document.getElementById("editor-title");
    const questionField = document.getElementById("editor-question");
    const explanationField = document.getElementById("editor-explanation");
    const editorAnswer = document.getElementById("editor-answer-number");
    const optionsContainer = document.getElementById("editor-distractors");

    const question = quiz.questions[currentQuestionIndex];

    // Set initial values
    titleField.innerHTML = `<textarea></textarea>`;
    titleField.querySelector("textarea").value = quiz.title;

    questionField.innerHTML = `<textarea></textarea>`;
    questionField.querySelector("textarea").value = question.question;

    explanationField.innerHTML = `<textarea></textarea>`;
    explanationField.querySelector("textarea").value =
        question.explanation || "";

    editorAnswer.value = question.correct_index + 1;

    optionsContainer.innerHTML = "";

    question.options.forEach((option) => {
        optionsContainer.appendChild(addEditorOption(option));
    });
}

// Copying
function formatQuestionAsText(question, index) {
    const lines = [];

    lines.push(`Question ${index + 1}: ${question.question}`);
    lines.push("");

    question.options.forEach((option, i) => {
        const letter = String.fromCharCode(65 + i);
        lines.push(`${letter}. ${option}`);
    });

    return lines.join("\n");
}

function formatAnswerKey(questions) {
    const lines = [
        "Answer Key:",
        "",
        "| Question | Correct Answer | Explanation |",
        "| --- | --- | --- |",
    ];

    questions.forEach((question, index) => {
        const correctLetter = String.fromCharCode(65 + question.correct_index);

        const escapeTableCell = (text) =>
            String(text ?? "")
                .replace(/\|/g, "\\|")
                .replace(/\n/g, " ");

        lines.push(
            `| ${index + 1} | ${correctLetter} | ${escapeTableCell(question.explanation || "")} |`,
        );
    });

    return lines.join("\n");
}

function formatQuizAsText() {
    const lines = [quiz.title, ""];

    quiz.questions.forEach((question, index) => {
        lines.push(formatQuestionAsText(question, index));
        lines.push("");
    });

    lines.push(formatAnswerKey(quiz.questions));

    return lines.join("\n").trim();
}

function copyToClipboard(text, successMessage) {
    if (navigator.clipboard?.writeText) {
        navigator.clipboard
            .writeText(text)
            .then(() => showEditorAlert(successMessage))
            .catch(() => showManualCopyPrompt(text));
    } else {
        showManualCopyPrompt(text);
    }
}

function showManualCopyPrompt(text) {
    showEditorAlert(
        "Clipboard access isn't available here. You may select and copy the text from the console.",
    );
    console.log(text);
}

function copyQuiz() {
    copyToClipboard(formatQuizAsText(), "Quiz copied to clipboard.");
}

function copyQuestion() {
    const question = quiz.questions[currentQuestionIndex];

    const text = [
        formatQuestionAsText(question, currentQuestionIndex),
        "",
        formatAnswerKey([question]),
    ].join("\n");

    copyToClipboard(text, "Question copied to clipboard.");
}

function addEditorOption(value) {
    const article = document.createElement("article");

    const textarea = document.createElement("textarea");
    textarea.value = value;

    const insertBtn = document.createElement("button");
    insertBtn.textContent = "+";
    insertBtn.onclick = () => {
        article.after(addEditorOption(""));
    };

    const deleteBtn = document.createElement("button");
    deleteBtn.textContent = "⌦";

    const promptDiv = document.createElement("div");
    promptDiv.className = "delete-prompt";

    const confirmBtn = document.createElement("button");
    confirmBtn.textContent = "Confirm";
    confirmBtn.onclick = () => article.remove();

    const cancelBtn = document.createElement("button");
    cancelBtn.textContent = "Cancel";
    cancelBtn.onclick = () => {
        promptDiv.style.display = "none";
    };

    deleteBtn.onclick = () => {
        promptDiv.style.display = "flex";
    };

    promptDiv.appendChild(confirmBtn);
    promptDiv.appendChild(cancelBtn);

    article.appendChild(insertBtn);
    article.appendChild(deleteBtn);
    article.appendChild(promptDiv);
    article.appendChild(textarea);

    return article;
}

function showEditorPrompt(
    message,
    onYes = null,
    onNo = null,
    yesText = "yes",
    noText = "no",
) {
    const prompt = document.getElementById("editor-close");
    const messageElement = document.getElementById("editor-prompt-message");
    const yesButton = document.getElementById("editor-prompt-yes");
    const noButton = document.getElementById("editor-prompt-no");
    messageElement.textContent = message;
    yesButton.textContent = yesText;
    noButton.textContent = noText;
    yesButton.style.display = "";
    noButton.style.display = "";
    yesButton.onclick = () => {
        prompt.classList.remove("visible");
        if (onYes) onYes();
    };
    noButton.onclick = () => {
        prompt.classList.remove("visible");
        if (onNo) onNo();
    };
    prompt.classList.add("visible");
}

function showEditorAlert(message) {
    const prompt = document.getElementById("editor-close");
    const messageElement = document.getElementById("editor-prompt-message");
    const yesButton = document.getElementById("editor-prompt-yes");
    const noButton = document.getElementById("editor-prompt-no");
    messageElement.textContent = message;
    yesButton.textContent = "OK";
    yesButton.style.display = "";
    noButton.style.display = "none";
    yesButton.onclick = () => {
        prompt.classList.remove("visible");
    };
    prompt.classList.add("visible");
}

// Returns false if the selected answer index does not exist in the DOM anymore
function validateAnswerIndex() {
    const answerInput = document.querySelector("#editor-answer-number");

    const val = parseInt(answerInput.value) - 1;

    const optionsContainer = document.getElementById("editor-distractors");
    const options = optionsContainer.querySelectorAll("article");

    if (val < 0 || val >= options.length) {
        answerInput.classList.add("input-error");
        showEditorAlert("Invalid Index: The selected option no longer exists.");
        return false;
    }

    return true;
}

function closeEditorConfirm() {
    showEditorPrompt(
        "Exit? Unsaved changes will be lost.",
        closeEditor,
        null,
        "yes",
        "no",
    );
}

function saveEdit() {
    if (!validateAnswerIndex()) {
        return;
    }

    // Extract data from DOM
    const newTitleText = document.querySelector("#editor-title textarea").value;
    const newQuestionText = document.querySelector(
        "#editor-question textarea",
    ).value;
    const newIndex =
        parseInt(document.querySelector("#editor-answer-number").value) - 1;
    const optionsContainer = document.getElementById("editor-distractors");
    const updatedOptions = Array.from(
        optionsContainer.querySelectorAll("textarea"),
    ).map((ta) => ta.value);

    const newExplanationText = document.querySelector(
        "#editor-explanation textarea",
    ).value;

    // Track whether the title was changed
    const titleChanged = quiz.title !== newTitleText;
    quiz.title = newTitleText;
    document.getElementById("title").textContent = newTitleText;

    // Update global state
    quiz.questions[currentQuestionIndex].question = newQuestionText;
    quiz.questions[currentQuestionIndex].correct_index = newIndex;
    quiz.questions[currentQuestionIndex].options = updatedOptions;
    quiz.questions[currentQuestionIndex].explanation = newExplanationText;

    // Persist the actual changes (locally)
    if (saveLocalEdit(currentQuestionIndex, titleChanged)) {
        showEditorAlert("Changes saved.");
    }
}

function closeEditor() {
    const questionBox = document.querySelector(".question-box");
    const editor = document.getElementById("editor");
    const prompt = document.getElementById("editor-close");

    prompt.classList.remove("visible");

    editor.style.display = "none";

    // Reset UI state
    const options = document.getElementById("editor-distractors");
    options.innerHTML = "";

    questionBox.style.display = "";

    renderQuiz();
}

function getQuizEditsKey() {
    return `quizEdits_${quizStorageKey}`;
}

function saveLocalEdit(index, titleChanged) {
    const key = getQuizEditsKey();

    let edits = {};

    try {
        edits = JSON.parse(localStorage.getItem(key)) || {};
    } catch {
        edits = {};
    }

    if (titleChanged) {
        edits.title = quiz.title;
    }

    edits[index] = quiz.questions[index];

    try {
        localStorage.setItem(key, JSON.stringify(edits));
        console.log("Saved edit:", key, edits);
        return true;
    } catch (e) {
        console.error("Failed to save edit:", e);
        return false;
    }
}

function loadQuizEdits() {
    const key = getQuizEditsKey();

    try {
        const edits = JSON.parse(localStorage.getItem(key));

        if (!edits) {
            return;
        }

        if (edits.title !== undefined) {
            quiz.title = edits.title;
        }

        // Load edited questions
        for (const [index, question] of Object.entries(edits)) {
            const i = Number(index);
            if (Number.isInteger(i) && i >= 0 && i < quiz.questions.length) {
                quiz.questions[i] = question;
            }
        }
    } catch (e) {
        console.error("Failed to load quiz edits:", e);
    }
}

function hashQuiz(quiz) {
    // Hash derived from the quiz's content to avoid overlap
    const data = JSON.stringify(quiz);

    let hash = 0;
    for (let i = 0; i < data.length; i++) {
        hash = (hash << 5) - hash + data.charCodeAt(i);
        hash |= 0;
    }

    return `currentQuestionIndex_${hash >>> 0}`;
}

function getStoredQuestionIndex() {
    try {
        const index = Number(
            localStorage.getItem(`currentQuestionIndex_${quizStorageKey}`),
        );

        if (!Number.isInteger(index)) {
            return 0;
        }

        return Math.max(0, Math.min(index, quiz.questions.length - 1));
    } catch {
        return 0;
    }
}

function setStoredQuestionIndex(value) {
    try {
        localStorage.setItem(
            `currentQuestionIndex_${quizStorageKey}`,
            String(value),
        );
    } catch (e) {
        // Ignore if storage is unavailable
    }
}

loadMathJax().then(() => {
    if (window.MathJax?.startup?.promise) {
        MathJax.startup.promise.then(renderQuiz);
    } else {
        renderQuiz();
    }
});
