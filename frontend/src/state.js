import { hashQuiz, getStoredQuestionIndex } from "./persistence/progress.js";
import { loadQuestionOrder } from "./persistence/question_order.js";

export const UNANSWERED = 0;
export const CORRECT = 1;
export const WRONG = 2;
export const SKIPPED = 3;

export const state = {
  mathReady: false,

  quiz: null,

  mode: null,

  wrongAnswerCount: 0,

  optionButtons: [],
  currentQuestion: null,

  answerRevealed: false,
  currentQuestionIndex: 0,

  questionOrder: [],
  questionSRSQueue: null,
  srs: false,
  srsQueueSize: 20,
  request_retention: 0.9,

  // Maximum level before removing from queue
  srsLevel: 5,

  questionResults: [],
  questionAnswers: [],

  defaultStartDate: Date.now(),

  quizStorageKey: null,

  timer: {
    visible: false,
    start: null,
    elapsed: 0,
    interval: null,
  },
};

export function initializeState(quiz) {
  state.quiz = quiz;
  state.quizStorageKey = hashQuiz(quiz);
  state.currentQuestionIndex = getStoredQuestionIndex(
    state.quizStorageKey,
    state.quiz.questions.length,
  );
  state.currentQuestion = null;
  state.optionButtons = [];
  state.wrongAnswerCount = 0;
  state.answerRevealed = false;

  state.questionOrder = loadQuestionOrder(
    state.quizStorageKey,
    state.quiz.questions.length,
  );

  state.questionResults = new Array(quiz.questions.length).fill(UNANSWERED);
  state.questionAnswers = new Array(quiz.questions.length).fill(null);

  state.defaultStartDate = Date.now();
}
