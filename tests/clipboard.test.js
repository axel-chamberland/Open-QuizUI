import { beforeEach, describe, expect, it, vi } from "vitest";

import { state } from "../frontend/src/state.js";
import {
  copyQuestion,
  copyQuiz,
  copyQuizAsFlashcards,
} from "../frontend/src/shared/clipboard.js";

vi.mock("../frontend/src/shared/markdown.js", () => ({
  toMarkdown: (text) => text,
}));

describe("clipboard", () => {
  let writeText;

  beforeEach(() => {
    writeText = vi.fn().mockResolvedValue(undefined);

    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: {
        writeText,
      },
    });

    state.quiz = {
      title: "Test Quiz",
      questions: [
        {
          question: "Question A",
          options: ["A1", "A2"],
          correct_index: 0,
          explanation: "Explanation A",
        },
        {
          question: "Question B",
          options: ["B1", "B2"],
          correct_index: 1,
          explanation: "Explanation B",
        },
        {
          question: "Question C",
          options: ["C1", "C2"],
          correct_index: 0,
          explanation: "Explanation C",
        },
      ],
    };

    state.questionOrder = [2, 0, 1];
    state.currentQuestionIndex = 1;
  });

  describe("copyQuestion", () => {
    it("copies the current question", async () => {
      await copyQuestion();

      expect(writeText).toHaveBeenCalledOnce();
      expect(writeText).toHaveBeenCalledWith(
        expect.stringContaining("Question 1: Question B"),
      );
    });

    it("copies the formatted current question", async () => {
      await copyQuestion();

      expect(writeText).toHaveBeenCalledOnce();
      expect(writeText).toHaveBeenCalledWith(
        `Test Quiz

Question 1: Question B

A. B1
B. B2

Answer Key:

| Question | Correct Answer | Explanation |
| --- | --- | --- |
| 1 | B | Explanation B |`,
      );
    });

    it("copies a flashcard question as a flashcard table", async () => {
      state.quiz.questions[1].options = ["Answer"];

      await copyQuestion();

      expect(writeText).toHaveBeenCalledOnce();
      expect(writeText).toHaveBeenCalledWith(
        `Test Quiz

| Question | Answer | Explanation |
| --- | --- | --- |
| Question B | Answer | Explanation B |`,
      );

      expect(state.quiz.questions[1].options).toEqual(["Answer"]);
    });
  });

  describe("copyQuiz", () => {
    it("does not modify the original quiz questions", async () => {
      const originalQuestions = state.quiz.questions;

      await copyQuiz();

      expect(state.quiz.questions).toBe(originalQuestions);
      expect(state.quiz.questions.map((q) => q.question)).toEqual([
        "Question A",
        "Question B",
        "Question C",
      ]);
    });
    it("copies the quiz using questionOrder", async () => {
      await copyQuiz();

      expect(writeText).toHaveBeenCalledOnce();
      expect(writeText).toHaveBeenCalledWith(
        `Test Quiz

Question 1: Question C

A. C1
B. C2

Question 2: Question A

A. A1
B. A2

Question 3: Question B

A. B1
B. B2

Answer Key:

| Question | Correct Answer | Explanation |
| --- | --- | --- |
| 1 | A | Explanation C |
| 2 | A | Explanation A |
| 3 | B | Explanation B |`,
      );
    });

    it("copies a quiz of flashcards as a flashcard table", async () => {
      state.quiz.questions = [
        {
          question: "Card A",
          options: ["A1"],
          correct_index: 0,
          explanation: "Explanation A",
        },
        { question: "Card B", options: ["B1"], correct_index: 0 },
      ];

      state.questionOrder = [1, 0];

      await copyQuiz();

      expect(writeText).toHaveBeenCalledWith(
        `Test Quiz

| Question | Answer | Explanation |
| --- | --- | --- |
| Card B | B1 |  |
| Card A | A1 | Explanation A |`,
      );
    });

    it("keeps a second choice for a flashcard in a quiz that holds choices", async () => {
      state.quiz.questions[1] = {
        question: "Question B",
        options: ["Answer"],
        correct_index: 0,
        explanation: "Explanation B",
      };

      await copyQuiz();

      expect(writeText).toHaveBeenCalledWith(
        `Test Quiz

Question 1: Question C

A. C1
B. C2

Question 2: Question A

A. A1
B. A2

Question 3: Question B

A. Answer
B. N/A

Answer Key:

| Question | Correct Answer | Explanation |
| --- | --- | --- |
| 1 | A | Explanation C |
| 2 | A | Explanation A |
| 3 | A | Explanation B |`,
      );
    });
  });

  describe("copyQuizAsFlashcards", () => {
    it("answers every question with its correct choice", async () => {
      await copyQuizAsFlashcards();

      expect(writeText).toHaveBeenCalledOnce();
      expect(writeText).toHaveBeenCalledWith(
        `Test Quiz

| Question | Answer | Explanation |
| --- | --- | --- |
| Question C | C1 | Explanation C |
| Question A | A1 | Explanation A |
| Question B | B2 | Explanation B |`,
      );
    });

    it("does not modify the original quiz questions", async () => {
      const originalQuestions = state.quiz.questions;

      await copyQuizAsFlashcards();

      expect(state.quiz.questions).toBe(originalQuestions);
      expect(state.quiz.questions.map((q) => q.question)).toEqual([
        "Question A",
        "Question B",
        "Question C",
      ]);
    });
  });
});
