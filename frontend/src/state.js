import { hashQuiz, getStoredQuestionIndex } from "./persistence/progress.js";
import { loadQuestionOrder } from "./persistence/question_order.js";
import { loadQuizEdits } from "./persistence/quiz_edits.js";
import { loadQuestionRemovals } from "./persistence/question_removals.js";

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

  /*
   * Number of questions the quiz itself has. Every question from here
   * on was added in the editor.
   */
  builtInQuestionCount: 0,

  /*
   * Indexes of the quiz's own questions deleted in the editor. They
   * stay in state.quiz.questions - see deleteQuestion - but are left
   * out of the navigation order.
   */
  removedQuestions: new Set(),

  /*
   * FSRS scheduler parameters; see srs.js. Values may be changed
   * per-quiz in the editor's additional settings.
   */
  srsConfig: {
    request_retention: 0.9,
    maximum_interval: 365,
    enable_fuzz: true,
    enable_short_term: true,
  },

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

/**
 * Builds a blank question for a question the user adds in the editor.
 *
 * The option count follows the quiz's last question, so a new question
 * starts out shaped like the rest of the quiz.
 *
 * @returns {object} Blank question, ready to be edited.
 */
export function createQuestionTemplate() {
  const questions = state.quiz.questions;
  const lastQuestion = questions[questions.length - 1];
  const optionCount = lastQuestion?.options?.length >= 2
    ? lastQuestion.options.length
    : 2;

  return {
    question: "",
    options: new Array(optionCount).fill(""),
    correct_index: 0,
    explanation: "",
  };
}

/**
 * Appends a question to the quiz, along with everything indexed
 * alongside it: its slot in the navigation order, its result and its
 * recorded answer.
 *
 * Questions are only ever appended, never inserted, so every index
 * already stored in the browser keeps pointing at the same question.
 *
 * @param {object} question Question to append.
 * @returns {number} Index the question was appended at.
 */
export function appendQuestion(question) {
  const index = state.quiz.questions.length;

  state.quiz.questions.push(question);
  state.questionOrder.push(index);
  state.questionResults[index] = UNANSWERED;
  state.questionAnswers[index] = null;

  return index;
}

/**
 * Removes an appended question from the quiz, dropping its slot in the
 * navigation order, its result and its recorded answer, and shifting
 * the questions after it down by one so they keep their identity.
 *
 * @param {number} index Index returned by appendQuestion.
 * @returns {void}
 */
export function removeAppendedQuestion(index) {
  state.quiz.questions.splice(index, 1);
  state.questionResults.splice(index, 1);
  state.questionAnswers.splice(index, 1);

  state.questionOrder = state.questionOrder
    .filter((item) => item !== index)
    .map((item) => (item > index ? item - 1 : item));
}

export function initializeState(quiz) {
  state.quiz = quiz;
  state.quizStorageKey = hashQuiz(quiz);
  state.builtInQuestionCount = quiz.questions.length;

  /*
   * Deleted questions are known before the order is loaded, so they can
   * be left out of it.
   */
  state.removedQuestions = loadQuestionRemovals(state.quizStorageKey);

  /*
   * Load the stored edits first: questions added in the editor are
   * stored past the end of the quiz, so they have to be back in place
   * before the order and the per-question state are built, or they
   * would be treated as indexes that no longer exist.
   */
  loadQuizEdits(state);

  state.currentQuestion = null;
  state.optionButtons = [];
  state.wrongAnswerCount = 0;
  state.answerRevealed = false;

  state.questionOrder = loadQuestionOrder(
    state.quizStorageKey,
    state.quiz.questions.length,
    state.removedQuestions,
  );

  state.currentQuestionIndex = getStoredQuestionIndex(
    state.quizStorageKey,
    state.quiz.questions.length,
  );

  // The stored position can point at a question deleted since.
  if (state.removedQuestions.has(state.currentQuestionIndex)) {
    state.currentQuestionIndex = state.questionOrder[0] ?? 0;
  }

  state.questionResults = new Array(quiz.questions.length).fill(UNANSWERED);
  state.questionAnswers = new Array(quiz.questions.length).fill(null);

  state.defaultStartDate = Date.now();
}
