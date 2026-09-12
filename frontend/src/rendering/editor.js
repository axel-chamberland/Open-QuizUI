import { state } from "../state.js";
import { renderQuiz } from "./mcq.js";
import { saveLocalEdit } from "../persistence/quiz_edits.js";

document
    .getElementById("editor-answer-number")
    .addEventListener("input", (e) => {
        e.target.value = e.target.value.replace(/\D/g, "");
    });



export function confirmRestart() {
    document.getElementById("restart-confirm").style.display = "flex";
}

export function cancelRestart() {
    document.getElementById("restart-confirm").style.display = "none";
}


export function openEditor() {
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

    // Set initial values
    titleField.innerHTML = `<textarea></textarea>`;
    titleField.querySelector("textarea").value = state.quiz.title;

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

// Alerts don't work in iframes, so we use a custom alert div
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

export function closeEditorConfirm() {
    showEditorPrompt(
        "Exit? Unsaved changes will be lost.",
        closeEditor,
        null,
        "yes",
        "no",
    );
}

export function saveEdit() {
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
    const titleChanged = state.quiz.title !== newTitleText;
    state.quiz.title = newTitleText;

    setQuizTitle(state.quiz.title);

    // Update global state
    state.quiz.questions[state.currentQuestionIndex].question = newQuestionText;
    state.quiz.questions[state.currentQuestionIndex].correct_index = newIndex;
    state.quiz.questions[state.currentQuestionIndex].options = updatedOptions;
    state.quiz.questions[state.currentQuestionIndex].explanation = newExplanationText;

    // Persist the actual changes (locally)
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

    // Reset UI state
    const options = document.getElementById("editor-distractors");
    options.innerHTML = "";

    questionBox.style.display = "";

    renderQuiz();
}
