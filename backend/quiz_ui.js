(() => {
    // src/persistence/progress.js
    function hashQuiz(quiz2) {
        const data = JSON.stringify(quiz2);
        let hash = 0;
        for (let i = 0; i < data.length; i++) {
            hash = (hash << 5) - hash + data.charCodeAt(i);
            hash |= 0;
        }
        return hash >>> 0;
    }
    function getProgressKey(quizStorageKey) {
        return `currentQuestionIndex_${quizStorageKey}`;
    }
    function getStoredQuestionIndex(quizStorageKey) {
        try {
            const index = Number(
                localStorage.getItem(getProgressKey(quizStorageKey))
            );
            if (!Number.isInteger(index)) {
                return 0;
            }
            return Math.max(0, Math.min(index, state.quiz.questions.length - 1));
        } catch {
            return 0;
        }
    }
    function setStoredQuestionIndex(quizStorageKey, value) {
        try {
            localStorage.setItem(
                getProgressKey(quizStorageKey),
                String(value)
            );
        } catch {
        }
    }

    // src/state.js
    var UNANSWERED = 0;
    var CORRECT = 1;
    var WRONG = 2;
    var SKIPPED = 3;
    var state = {
        mathReady: false,
        quiz: null,
        wrongAnswerCount: 0,
        optionButtons: [],
        currentQuestion: null,
        answerRevealed: false,
        currentQuestionIndex: 0,
        questionResults: [],
        questionAnswers: [],
        defaultStartDate: Date.now(),
        quizStorageKey: null,
        timer: {
            visible: false,
            start: null,
            elapsed: 0,
            interval: null
        }
    };
    function initializeState(quiz2) {
        state.quiz = quiz2;
        state.quizStorageKey = hashQuiz(quiz2);
        state.currentQuestionIndex = getStoredQuestionIndex(state.quizStorageKey);
        state.currentQuestion = null;
        state.optionButtons = [];
        state.wrongAnswerCount = 0;
        state.answerRevealed = false;
        state.questionResults = new Array(quiz2.questions.length).fill(UNANSWERED);
        state.questionAnswers = new Array(quiz2.questions.length).fill(null);
        state.defaultStartDate = Date.now();
    }

    // src/shared/markdown.js
    function renderMath(text, mathReady) {
        if (!text) return "";
        return text.replace(/\$(.+?)\$/g, (match, expr) => {
            if (mathReady && window.MathJax) {
                return match;
            }
            return `<code>${expr}</code>`;
        });
    }
    function escapeHtml(value) {
        return value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
    }
    function renderMarkdown2(text, mathReady) {
        if (!text) return "";
        const protectedParts = [];
        function protect(value) {
            const index = protectedParts.length;
            protectedParts.push(value);
            return `\uE000${index}\uE001`;
        }
        text = text.replace(
            /```(?:[^\n`]*)\n([\s\S]*?)```/g,
            (_, content) => protect(`<pre><code>${escapeHtml(content)}</code></pre>`)
        );
        text = text.replace(
            /`([^`]*?)`/g,
            (_, content) => protect(`<code>${escapeHtml(content)}</code>`)
        );
        text = text.replace(/\$\$[\s\S]*?\$\$/g, protect);
        text = text.replace(/\$(?!\$)[\s\S]*?\$(?!\$)/g, protect);
        const voidElements = /* @__PURE__ */ new Set([
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
            "wbr"
        ]);
        text = text.replace(
            /<\/?(\p{L}[\p{L}\p{N}-]*)(?:\s[^>]*)?>/gu,
            (match, tagName, offset, wholeText) => {
                const tag = tagName.toLowerCase();
                if (match.startsWith("</")) {
                    return match;
                }
                if (/\/>$/.test(match)) {
                    return match;
                }
                if (voidElements.has(tag)) {
                    return match;
                }
                const closingTag = new RegExp(`</${tag}\\s*>`, "iu");
                if (closingTag.test(wholeText.slice(offset + match.length))) {
                    return match;
                }
                return match.replace(/</g, "&lt;").replace(/>/g, "&gt;");
            }
        );
        text = text.replace(/\*\*(.*?)\*\*/g, "<b>$1</b>").replace(/\*(.*?)\*/g, "<i>$1</i>");
        text = text.replace(
            /\uE000(\d+)\uE001/g,
            (_, index) => protectedParts[Number(index)]
        );
        return renderMath(text, mathReady);
    }

    // src/rendering/mcq.js
    function showExplanation(question) {
        const explanationEl = document.getElementById("explanation");
        if (question.explanation) {
            explanationEl.innerHTML = renderMarkdown2(question.explanation, state.mathReady);
            explanationEl.style.display = "block";
            if (state.mathReady && window.MathJax) {
                window.MathJax.typesetPromise([explanationEl]).catch(
                    (err) => console.error("MathJax typesetting failed:", err)
                );
            }
        } else {
            explanationEl.innerHTML = "";
            explanationEl.style.display = "none";
        }
    }
    async function renderQuiz() {
        const questionBox = document.querySelector(".question-box");
        const questionText = questionBox.querySelector("#question");
        const optionsContainer = document.getElementById("options");
        const navigationContainer = questionBox.querySelector("#navigation");
        const explanationEl = document.getElementById("explanation");
        if (!state.quiz.questions || state.quiz.questions.length === 0) {
            document.getElementById("question").textContent = "No valid questions parsed";
            return;
        }
        questionText.innerHTML = renderMarkdown2(
            state.quiz.questions[state.currentQuestionIndex].question,
            state.mathReady
        );
        explanationEl.textContent = "";
        explanationEl.style.display = "none";
        optionsContainer.innerHTML = "";
        state.wrongAnswerCount = 0;
        state.optionButtons = [];
        state.currentQuestion = state.quiz.questions[state.currentQuestionIndex];
        state.currentQuestion.options.forEach((option, index) => {
            const button = document.createElement("button");
            button.innerHTML = renderMarkdown2(option, state.mathReady);
            button.className = "option";
            state.optionButtons.push(button);
            button.addEventListener("click", () => {
                handleAnswer(index, button);
            });
            optionsContainer.appendChild(button);
        });
        const prevButton = navigationContainer.querySelector("#prev-button");
        prevButton.disabled = state.currentQuestionIndex === 0;
        document.getElementById("question-scroll").scrollTop = 0;
        if (state.mathReady && window.MathJax) {
            try {
                await window.MathJax.typesetPromise();
            } catch (err) {
                console.error("MathJax typesetting failed:", err);
            }
        }
    }

    // src/persistence/stats.js
    function getStatsKey(quizStorageKey) {
        return `quizStats_${quizStorageKey}`;
    }
    function loadStats() {
        try {
            const data = JSON.parse(localStorage.getItem(getStatsKey(state.quizStorageKey)));
            if (Array.isArray(data?.results)) {
                state.questionResults = data.results;
            }
            if (Array.isArray(data?.answers)) {
                state.questionAnswers = data.answers;
            }
            if (data?.startDate) {
                state.defaultStartDate = data.startDate;
            }
        } catch {
            state.questionResults = new Array(state.quiz.questions.length).fill(UNANSWERED);
            state.questionAnswers = new Array(state.quiz.questions.length).fill(null);
            state.defaultStartDate = Date.now();
        }
    }
    function saveStats() {
        try {
            localStorage.setItem(
                getStatsKey(state.quizStorageKey),
                JSON.stringify({
                    results: state.questionResults,
                    answers: state.questionAnswers,
                    startDate: state.defaultStartDate
                })
            );
        } catch {
        }
    }

    // src/shared/formatting.js
    function formatTime(seconds) {
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = seconds % 60;
        return `${String(minutes).padStart(2, "0")}:${String(remainingSeconds).padStart(2, "0")}`;
    }
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
            "| --- | --- | --- |"
        ];
        questions.forEach((question, index) => {
            const correctLetter = String.fromCharCode(65 + question.correct_index);
            const escapeTableCell = (text) => String(text ?? "").replace(/\|/g, "\\|").replace(/\n/g, " ");
            lines.push(
                `| ${index + 1} | ${correctLetter} | ${escapeTableCell(question.explanation || "")} |`
            );
        });
        return lines.join("\n");
    }
    function formatQuizAsText(quiz2) {
        const lines = [quiz2.title, ""];
        quiz2.questions.forEach((question, index) => {
            lines.push(formatQuestionAsText(question, index));
            lines.push("");
        });
        lines.push(formatAnswerKey(quiz2.questions));
        return lines.join("\n").trim();
    }

    // src/timer.js
    var timerElement = document.getElementById("timer");
    function getTimerKey(quizStorageKey) {
        return `quizTimer_${quizStorageKey}`;
    }
    function loadTimer(state2) {
        try {
            const data = JSON.parse(localStorage.getItem(getTimerKey(state2.quizStorageKey)));
            state2.timer.elapsed = data?.elapsed || 0;
            state2.timer.start = data?.start || null;
        } catch {
            state2.timer.elapsed = 0;
            state2.timer.start = null;
        }
    }
    function saveTimer() {
        try {
            localStorage.setItem(
                getTimerKey(state.quizStorageKey),
                JSON.stringify({
                    elapsed: state.timer.elapsed,
                    start: state.timer.start
                })
            );
        } catch {
        }
    }
    function updateTimer() {
        if (!state.timer.start) return;
        const elapsed = state.timer.elapsed + Math.floor((Date.now() - state.timer.start) / 1e3);
        timerElement.textContent = formatTime(elapsed);
    }
    function toggleTimer() {
        state.timer.visible = !state.timer.visible;
        timerElement.classList.toggle("visible", state.timer.visible);
        if (state.timer.visible) {
            loadTimer(state);
            if (!state.timer.start) {
                state.timer.start = Date.now();
                saveTimer(state);
            }
            updateTimer(timerElement);
            state.timer.interval = setInterval(updateTimer, 1e3, timerElement);
        } else {
            if (state.timer.start) {
                state.timer.elapsed += Math.floor((Date.now() - state.timer.start) / 1e3);
                state.timer.start = null;
                saveTimer(state);
            }
            clearInterval(state.timer.interval);
            state.timer.interval = null;
        }
    }

    // src/rendering/results.js
    async function renderResults() {
        const questionBox = document.querySelector(".question-box");
        const results2 = document.getElementById("results");
        questionBox.style.display = "none";
        results2.style.display = "";
        const correct = state.questionResults.filter((x) => x === CORRECT).length;
        const wrong = state.questionResults.filter((x) => x === WRONG).length;
        const unanswered = state.questionResults.filter((x) => x === UNANSWERED).length;
        const skipped = state.questionResults.filter((x) => x === SKIPPED).length;
        const total = state.quiz.questions.length;
        const answered = correct + wrong;
        const accuracy = answered > 0 ? correct / answered * 100 : 0;
        const elapsed = state.timer.visible ? state.timer.elapsed + Math.floor((Date.now() - state.timer.start) / 1e3) : Math.floor((Date.now() - state.defaultStartDate) / 1e3);
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
                        "chart-skipped"
                    ]
                }
            ]
        };
        document.getElementById("score").textContent = `Score: ${correct}/${wrong + correct}`;
        document.getElementById("accuracy").textContent = `Accuracy: ${accuracy.toFixed(1)}%`;
        document.getElementById("correct").textContent = `Correct: ${correct}`;
        document.getElementById("wrong").textContent = `Wrong: ${wrong}`;
        document.getElementById("unanswered").textContent = `Unanswered: ${unanswered}`;
        document.getElementById("skipped").textContent = `Skipped: ${skipped}`;
        document.getElementById("time").textContent = `Time: ${formatTime(elapsed)}`;
        document.getElementById("averageTime").textContent = `Average time per question: ${formatTime(Math.floor(elapsed / total))}`;
        createDonutChart(document.getElementById("statsChart"), chartData);
        showCorrectionSheet();
        if (state.mathReady && window.MathJax) {
            try {
                await MathJax.typesetPromise([
                    document.getElementById("question-corrections")
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
        const arcs = values.map((value, i) => {
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
        }).join("");
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
            const userAnswer = state.questionResults[index] === SKIPPED ? "Skipped" : userIndex !== null ? question.options[userIndex] : "Unanswered";
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

${question.explanation ? `
<p>
    <strong>Explanation:</strong>
    ${renderMarkdown(question.explanation, state.mathReady)}
</p>
` : ""}
`;
            container.appendChild(article);
        }
    }
    var questionNumber = document.getElementById("question-number");
    function restartQuiz() {
        state.currentQuestionIndex = 0;
        questionNumber.value = 1;
        state.answerRevealed = false;
        state.wrongAnswerCount = 0;
        state.questionResults = new Array(state.quiz.questions.length).fill(UNANSWERED);
        state.questionAnswers = new Array(state.quiz.questions.length).fill(null);
        document.getElementById("question-corrections").innerHTML = "";
        clearInterval(state.timer.interval);
        state.timer.interval = null;
        state.timer.elapsed = 0;
        state.timer.start = state.timer.visible ? Date.now() : null;
        state.defaultStartDate = Date.now();
        const timerElement2 = document.getElementById("timer");
        if (state.timer.visible) {
            updateTimer();
            state.timer.interval = setInterval(updateTimer, 1e3);
        } else {
            timerElement2.textContent = formatTime(0);
        }
        saveTimer();
        setStoredQuestionIndex(state.quizStorageKey, 0);
        const results2 = document.getElementById("results");
        const questionBox = document.querySelector(".question-box");
        results2.style.display = "none";
        questionBox.style.display = "";
        document.getElementById("restart-confirm").style.display = "none";
        renderQuiz();
    }

    // src/quiz.js
    var results = document.getElementById("results");
    function nextQuestion() {
        if (state.currentQuestionIndex >= state.quiz.questions.length - 1 && results.style.display === "none") {
            renderResults();
            return;
        }
        goTo(state.currentQuestionIndex + 1);
    }
    function prevQuestion() {
        const results2 = document.getElementById("results");
        if (results2.style.display !== "none") {
            results2.style.display = "none";
            document.querySelector(".question-box").style.display = "";
            renderQuiz();
            return;
        }
        if (state.currentQuestionIndex <= 0) return;
        goTo(state.currentQuestionIndex - 1);
    }
    function goTo(question_index) {
        question_index = Math.max(
            0,
            Math.min(question_index, state.quiz.questions.length - 1)
        );
        state.currentQuestionIndex = question_index;
        setStoredQuestionIndex(state.quizStorageKey, state.currentQuestionIndex);
        state.answerRevealed = false;
        const questionNumber2 = document.getElementById("question-number");
        questionNumber2.value = state.currentQuestionIndex + 1;
        renderQuiz();
    }
    function handleAnswer(index, button) {
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
            state.optionButtons.forEach((btn) => btn.disabled = true);
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
    function revealAnswer() {
        state.answerRevealed = true;
        if (state.questionResults[state.currentQuestionIndex] === UNANSWERED) {
            state.questionResults[state.currentQuestionIndex] = SKIPPED;
            saveStats();
        }
        state.currentQuestion = state.quiz.questions[state.currentQuestionIndex];
        const optionsContainer = document.getElementById("options");
        const buttons = optionsContainer.querySelectorAll("button");
        buttons[state.currentQuestion.correct_index].classList.add("correct");
        showExplanation(state.currentQuestion);
    }

    // src/shared/download.js
    function downloadQuizHTML(filename = state.quiz.title) {
        const appData2 = {
            enableMathJax: state.ENABLE_MATHJAX,
            quiz: state.quiz
        };
        const documentClone = document.documentElement.cloneNode(true);
        const dataScript = documentClone.querySelector("#app-data");
        if (!dataScript) {
            throw new Error("Could not find #app-data");
        }
        dataScript.textContent = JSON.stringify(appData2, null, 2);
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

    // src/shared/clipboard.js
    function copyQuestion() {
        const question = state.quiz.questions[state.currentQuestionIndex];
        const text = [
            formatQuestionAsText(question, state.currentQuestionIndex),
            "",
            formatAnswerKey([question])
        ].join("\n");
        copyToClipboard(text, "Question copied to clipboard.");
    }
    function copyQuiz() {
        copyToClipboard(formatQuizAsText(state.quiz), "Quiz copied to clipboard.");
    }
    async function copyToClipboard(text) {
        if (navigator.clipboard?.writeText) {
            try {
                await navigator.clipboard.writeText(text);
                return true;
            } catch {
            }
        }
        return false;
    }

    // src/persistence/quiz_edits.js
    function getQuizEditsKey(quizStorageKey) {
        return `quizEdits_${quizStorageKey}`;
    }
    function saveLocalEdit(index, titleChanged) {
        const key = getQuizEditsKey(state.quizStorageKey);
        let edits = {};
        try {
            edits = JSON.parse(localStorage.getItem(key)) || {};
        } catch {
            edits = {};
        }
        if (titleChanged) {
            edits.title = state.quiz.title;
        }
        edits[index] = state.quiz.questions[index];
        try {
            localStorage.setItem(key, JSON.stringify(edits));
            console.log("Saved edit:", key, edits);
            return true;
        } catch (e) {
            console.error("Failed to save edit:", e);
            return false;
        }
    }
    function loadQuizEdits(state2) {
        const key = getQuizEditsKey(state2.quizStorageKey);
        try {
            const edits = JSON.parse(localStorage.getItem(key));
            if (!edits) {
                return;
            }
            if (edits.title !== void 0) {
                state2.quiz.title = edits.title;
            }
            for (const [index, question] of Object.entries(edits)) {
                const i = Number(index);
                if (Number.isInteger(i) && i >= 0 && i < state2.quiz.questions.length) {
                    state2.quiz.questions[i] = question;
                }
            }
        } catch (e) {
            console.error("Failed to load quiz edits:", e);
        }
    }

    // src/rendering/editor.js
    document.getElementById("editor-answer-number").addEventListener("input", (e) => {
        e.target.value = e.target.value.replace(/\D/g, "");
    });
    function confirmRestart() {
        document.getElementById("restart-confirm").style.display = "flex";
    }
    function cancelRestart() {
        document.getElementById("restart-confirm").style.display = "none";
    }
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
        const question = state.quiz.questions[state.currentQuestionIndex];
        titleField.innerHTML = `<textarea></textarea>`;
        titleField.querySelector("textarea").value = state.quiz.title;
        questionField.innerHTML = `<textarea></textarea>`;
        questionField.querySelector("textarea").value = question.question;
        explanationField.innerHTML = `<textarea></textarea>`;
        explanationField.querySelector("textarea").value = question.explanation || "";
        editorAnswer.value = question.correct_index + 1;
        optionsContainer.innerHTML = "";
        question.options.forEach((option) => {
            optionsContainer.appendChild(addEditorOption(option));
        });
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
        deleteBtn.textContent = "\u2326";
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
    function showEditorPrompt(message, onYes = null, onNo = null, yesText = "yes", noText = "no") {
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
            "no"
        );
    }
    function saveEdit() {
        if (!validateAnswerIndex()) {
            return;
        }
        const newTitleText = document.querySelector("#editor-title textarea").value;
        const newQuestionText = document.querySelector(
            "#editor-question textarea"
        ).value;
        const newIndex = parseInt(document.querySelector("#editor-answer-number").value) - 1;
        const optionsContainer = document.getElementById("editor-distractors");
        const updatedOptions = Array.from(
            optionsContainer.querySelectorAll("textarea")
        ).map((ta) => ta.value);
        const newExplanationText = document.querySelector(
            "#editor-explanation textarea"
        ).value;
        const titleChanged = state.quiz.title !== newTitleText;
        state.quiz.title = newTitleText;
        document.getElementById("title").textContent = newTitleText;
        state.quiz.questions[state.currentQuestionIndex].question = newQuestionText;
        state.quiz.questions[state.currentQuestionIndex].correct_index = newIndex;
        state.quiz.questions[state.currentQuestionIndex].options = updatedOptions;
        state.quiz.questions[state.currentQuestionIndex].explanation = newExplanationText;
        if (saveLocalEdit(state.currentQuestionIndex, titleChanged)) {
            showEditorAlert("Changes saved.");
        }
    }
    function closeEditor() {
        const questionBox = document.querySelector(".question-box");
        const editor = document.getElementById("editor");
        const prompt = document.getElementById("editor-close");
        prompt.classList.remove("visible");
        editor.style.display = "none";
        const options = document.getElementById("editor-distractors");
        options.innerHTML = "";
        questionBox.style.display = "";
        renderQuiz();
    }

    // src/ui/fullscreen.js
    var pseudoFullscreenState = null;
    async function toggleFullscreen() {
        if (document.fullscreenElement || document.webkitFullscreenElement) {
            if (document.exitFullscreen) await document.exitFullscreen();
            else document.webkitExitFullscreen?.();
            return;
        }
        if (document.documentElement.classList.contains("pseudo-fullscreen-active")) {
            document.documentElement.classList.remove("pseudo-fullscreen-active");
            exitPseudoFullscreen();
            return;
        }
        const root = document.documentElement;
        if (root.requestFullscreen) {
            try {
                await root.requestFullscreen();
                return;
            } catch {
            }
        } else if (root.webkitRequestFullscreen) {
            root.webkitRequestFullscreen();
            return;
        }
        document.documentElement.classList.add("pseudo-fullscreen-active");
        enterPseudoFullscreen();
    }
    function enterPseudoFullscreen() {
        const iframe = window.frameElement;
        const topBody = window.top.document.body;
        topBody.classList.add("pseudo-fullscreen-active");
        pseudoFullscreenState = {
            scrollX: window.top.scrollX,
            scrollY: window.top.scrollY,
            elements: []
        };
        let el = iframe;
        while (el && el !== document.body) {
            pseudoFullscreenState.elements.push({
                el,
                style: el.getAttribute("style"),
                siblings: [...el.parentElement.children].filter((x) => x !== el).map((x) => [x, x.style.display])
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
        window.top.scrollTo(scrollX, scrollY);
        window.frameElement.scrollIntoView({
            block: "center",
            inline: "nearest"
        });
    }

    // src/ui/events.js
    function initializeEvents() {
        document.getElementById("prev-button").addEventListener("click", prevQuestion);
        document.getElementById("next-button").addEventListener("click", nextQuestion);
        document.getElementById("reveal-button").addEventListener("click", revealAnswer);
        document.getElementById("maximize-button").addEventListener("click", toggleFullscreen);
        document.getElementById("download-button").addEventListener("click", downloadQuizHTML);
        document.getElementById("timer-toggle").addEventListener("click", toggleTimer);
        document.getElementById("copy-all-button").addEventListener("click", copyQuiz);
        document.getElementById("copy-question-button").addEventListener("click", copyQuestion);
        document.getElementById("editor-button").addEventListener("click", openEditor);
        document.getElementById("results-back-button").addEventListener("click", prevQuestion);
        document.getElementById("results-maximize-button").addEventListener("click", toggleFullscreen);
        document.getElementById("results-download-button").addEventListener("click", downloadQuizHTML);
        document.getElementById("results-copy-all-button").addEventListener("click", copyQuiz);
        document.getElementById("restart-button").addEventListener("click", confirmRestart);
        document.getElementById("confirm-restart-button").addEventListener("click", restartQuiz);
        document.getElementById("cancel-restart-button").addEventListener("click", cancelRestart);
        document.getElementById("editor-save-button").addEventListener("click", saveEdit);
        document.getElementById("editor-copy-button").addEventListener("click", copyQuestion);
        document.getElementById("editor-maximize-button").addEventListener("click", toggleFullscreen);
        document.getElementById("editor-close-button").addEventListener("click", closeEditorConfirm);
        document.addEventListener("keydown", (e) => {
            if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
            const key = e.key.toLowerCase();
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
            if (key === "enter" || key == " ") {
                e.preventDefault();
                if (!state.answerRevealed) {
                    revealAnswer();
                } else {
                    nextQuestion();
                }
                return;
            }
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
        const questionBox = document.querySelector(".question-box");
        questionBox.addEventListener("click", (e) => {
            if (e.target.closest("button, input")) return;
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
        const questionSelector = document.getElementById("question-selector");
        const questionNumber2 = document.getElementById("question-number");
        questionSelector.addEventListener("click", () => {
            questionNumber2.focus();
            questionNumber2.select();
        });
        questionNumber2.addEventListener("input", () => {
            questionNumber2.value = questionNumber2.value.replace(/\D/g, "");
        });
        questionNumber2.addEventListener("change", () => {
            if (!questionNumber2.value) return;
            goTo(Number(questionNumber2.value) - 1);
        });
    }

    // src/shared/mathjax.js
    function loadMathJax(enabled) {
        if (!enabled) {
            state.mathReady = false;
            resolve(false);
            return;
        }
        window.MathJax = {
            tex: {
                inlineMath: [
                    ["$", "$"],
                    ["\\(", "\\)"]
                ]
            }
        };
        return new Promise((resolve2) => {
            const script = document.createElement("script");
            script.src = "https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js";
            script.onload = () => {
                state.mathReady = true;
                resolve2(true);
            };
            script.onerror = () => {
                state.mathReady = false;
                resolve2(false);
            };
            document.head.appendChild(script);
        });
    }

    // src/main.js
    var appData = JSON.parse(
        document.getElementById("app-data").textContent
    );
    var ENABLE_MATHJAX = appData.enableMathJax;
    var quiz = appData.quiz;
    try {
        if (window.top.document.body.classList.contains("pseudo-fullscreen-active")) {
            window.top.location.reload();
        }
    } catch {
    }
    initializeState(quiz);
    loadStats();
    loadQuizEdits(state);
    initializeEvents();
    var questionCount = document.getElementById("question-count");
    questionCount.textContent = quiz.questions.length;
    async function initializeQuiz() {
        await loadMathJax(ENABLE_MATHJAX);
        if (state.mathReady && window.MathJax?.startup?.promise) {
            await window.MathJax.startup.promise;
        }
        renderQuiz();
    }
    initializeQuiz();
})();

