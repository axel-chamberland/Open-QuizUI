
export function formatTime(seconds) {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;

    return `${String(minutes).padStart(2, "0")}:${String(remainingSeconds).padStart(2, "0")}`;
}

export function formatQuestionAsText(question, index) {
    const lines = [];

    lines.push(`Question ${index + 1}: ${question.question}`);
    lines.push("");

    question.options.forEach((option, i) => {
        const letter = String.fromCharCode(65 + i);
        lines.push(`${letter}. ${option}`);
    });

    return lines.join("\n");
}

export function formatAnswerKey(questions) {
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

export function formatQuizAsText(quiz) {
    const lines = [quiz.title, ""];

    quiz.questions.forEach((question, index) => {
        lines.push(formatQuestionAsText(question, index));
        lines.push("");
    });

    lines.push(formatAnswerKey(quiz.questions));

    return lines.join("\n").trim();
}

