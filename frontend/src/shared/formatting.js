import { toMarkdown } from "./markdown.js";

export function formatTime(seconds) {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;

    return `${String(minutes).padStart(2, "0")}:${String(remainingSeconds).padStart(2, "0")}`;
}

export function formatQuestionAsText(question, index) {
    const lines = [];

    const questionText = toMarkdown(
        question.question,
    );

    lines.push(`Question ${index + 1}: ${questionText}`);
    lines.push("");

    for (const [i, option] of question.options.entries()) {
        const letter = String.fromCharCode(65 + i);

        lines.push(
            `${letter}. ${toMarkdown(option)}`,
        );
    }

    return lines.join("\n");
}

export function formatAnswerKey(questions) {
    const lines = [
        "Answer Key:",
        "",
        "| Question | Correct Answer | Explanation |",
        "| --- | --- | --- |",
    ];

    const escapeTableCell = (text) =>
        String(text ?? "")
            .replace(/\|/g, "\\|")
            .replace(/\n/g, " ");

    for (const [index, question] of questions.entries()) {
        const correctLetter = String.fromCharCode(
            65 + question.correct_index,
        );

        const explanation = toMarkdown(
            question.explanation || "",
        );

        lines.push(
            `| ${index + 1} | ${correctLetter} | ${escapeTableCell(explanation)} |`,
        );
    }

    return lines.join("\n");
}

export function formatQuizAsText(quiz) {
    const lines = [
        toMarkdown(quiz.title),
        "",
    ];

    for (const [index, question] of quiz.questions.entries()) {
        lines.push(
            formatQuestionAsText(
                question,
                index,
            ),
        );
        lines.push("");
    }

    lines.push(
        formatAnswerKey(
            quiz.questions,
        ),
    );

    return lines.join("\n").trim();
}
