import { describe, it, expect, vi } from "vitest";
import {
  formatTime,
  formatQuestionAsText,
  formatAnswerKey,
  formatQuizAsText,
} from "../frontend/src/shared/formatting.js";

vi.mock("../frontend/src/shared/markdown.js", () => ({
  toMarkdown: vi.fn((text) => text),
}));

describe("formatTime", () => {
  it("formats minutes and seconds with leading zeros", () => {
    expect(formatTime(0)).toBe("00:00");
    expect(formatTime(65)).toBe("01:05");
    expect(formatTime(125)).toBe("02:05");
  });

  it("handles times longer than one hour", () => {
    expect(formatTime(100000)).toBe("1666:40");
  });
});

describe("formatQuestionAsText", () => {
  it("formats the question and options", () => {
    const question = {
      question: "What is 2 + 2?",
      options: ["3", "4", "5"],
    };

    expect(formatQuestionAsText(question, 0)).toBe(
      "Question 1: What is 2 + 2?\n\nA. 3\nB. 4\nC. 5",
    );
  });

  it("uses the correct question number", () => {
    const question = {
      question: "Question?",
      options: ["A"],
    };

    expect(formatQuestionAsText(question, 4)).toContain("Question 5:");
  });
});

describe("formatAnswerKey", () => {
  it("formats the correct answer and explanation", () => {
    const questions = [
      {
        correct_index: 1,
        explanation: "Because **4** is correct.",
      },
    ];

    expect(formatAnswerKey(questions)).toBe(
      "Answer Key:\n\n" +
        "| Question | Correct Answer | Explanation |\n" +
        "| --- | --- | --- |\n" +
        "| 1 | B | Because **4** is correct. |",
    );
  });

  it("escapes pipes in explanations", () => {
    const questions = [
      {
        correct_index: 0,
        explanation: "A | B",
      },
    ];

    expect(formatAnswerKey(questions)).toContain("| 1 | A | A \\| B |");
  });

  it("replaces newlines in explanations", () => {
    const questions = [
      {
        correct_index: 0,
        explanation: "Line one\nLine two",
      },
    ];

    expect(formatAnswerKey(questions)).toContain(
      "| 1 | A | Line one Line two |",
    );
  });

  it("handles a missing explanation", () => {
    const questions = [
      {
        correct_index: 0,
      },
    ];

    expect(formatAnswerKey(questions)).toContain("| 1 | A |  |");
  });
});

describe("formatQuizAsText", () => {
  it("formats the complete quiz", () => {
    const quiz = {
      title: "My Quiz",
      questions: [
        {
          question: "Question?",
          options: ["choice1", "choice2"],
          correct_index: 1,
          explanation: "Because choice2.",
        },
        {
          question: "Question2?",
          options: ["choice3", "choice4"],
          correct_index: 0,
          explanation: "Because choice3.",
        },
      ],
    };

    expect(formatQuizAsText(quiz)).toBe(
      "My Quiz\n\n" +
        "Question 1: Question?\n\n" +
        "A. choice1\n" +
        "B. choice2\n\n" +
        "Question 2: Question2?\n\n" +
        "A. choice3\n" +
        "B. choice4\n\n" +
        "Answer Key:\n\n" +
        "| Question | Correct Answer | Explanation |\n" +
        "| --- | --- | --- |\n" +
        "| 1 | B | Because choice2. |\n" +
        "| 2 | A | Because choice3. |",
    );
  });
});
