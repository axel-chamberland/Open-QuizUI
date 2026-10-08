import { state } from "./state.js";
import {
  loadQuestionSRSState,
  saveQuestionSRSState,
} from "./persistence/question_order.js";

/**
 * FSRS scheduler configuration.
 *
 * These values configure FSRS itself. No additional
 * application-specific scheduling rules are applied.
 */
const SRS_CONFIG = {
  request_retention: state.request_retention,
  maximum_interval: 365,
  enable_fuzz: true,
  enable_short_term: true,
};

/**
 * Rating values accepted from quiz.js.
 */
const VALID_RATINGS = new Set(["Again", "Hard", "Good", "Easy"]);

let fsrsPromise = null;
let fsrsModule = null;
let scheduler = null;

/**
 * Cards that have been introduced to the SRS system.
 *
 * Map:
 *   question index -> FSRS Card
 *
 * A card remains here even when it is removed from the
 * active session queue because its next FSRS review is
 * scheduled for the future.
 */
const cards = new Map();

/**
 * History of SRS changes made during the current session.
 *
 * This is runtime-only and is not persisted.
 */
const history = [];

/**
 * Lazily loads the FSRS library and creates the scheduler.
 *
 * @returns {Promise<boolean>}
 */
async function loadFSRS() {
  if (scheduler) return true;

  if (!fsrsPromise) {
    fsrsPromise = import("https://cdn.jsdelivr.net/npm/ts-fsrs@5.4.2/+esm");
  }

  try {
    fsrsModule = await fsrsPromise;
    scheduler = fsrsModule.fsrs(SRS_CONFIG);
    return true;
  } catch (error) {
    console.error("Failed to import FSRS:", error);
    fsrsPromise = null;
    fsrsModule = null;
    scheduler = null;
    return false;
  }
}

/**
 * Converts persisted FSRS date strings back into Date objects.
 *
 * JSON serialization converts Date objects into strings, while
 * ts-fsrs expects Date instances when operating on cards.
 *
 * @param {object} card
 * @returns {object}
 */
function restoreCard(card) {
  return {
    ...card,
    due: new Date(card.due),
    last_review: card.last_review ? new Date(card.last_review) : undefined,
  };
}

/**
 * Compares two active SRS queue entries by their FSRS due date.
 *
 * Earlier due dates are placed first. The question index is
 * used only as a deterministic tie-breaker.
 *
 * @param {{index: number, card: object}} a
 * @param {{index: number, card: object}} b
 * @returns {number}
 */
function compareSRSItems(a, b) {
  const aDue = new Date(a.card.due).getTime();
  const bDue = new Date(b.card.due).getTime();

  if (aDue !== bDue) {
    return aDue - bDue;
  }

  return a.index - b.index;
}

/**
 * Sorts the active SRS queue by FSRS due date.
 *
 * @returns {void}
 */
function sortSRSQueue() {
  state.questionSRSQueue.sort(compareSRSItems);
}

/**
 * Persists the complete FSRS state.
 *
 * Cards that are currently active in the session are marked
 * active: true. Cards whose next FSRS review is in the future
 * are retained in the card store but marked inactive.
 *
 * @param {string} quizStorageKey
 * @returns {void}
 */
function saveSRS(quizStorageKey) {
  const active = new Set(state.questionSRSQueue.map(({ index }) => index));

  saveQuestionSRSState(quizStorageKey, {
    queue: Array.from(cards, ([index, card]) => ({
      index,
      card,
      active: active.has(index),
    })),
  });
}

/**
 * Adds the next unseen question to the active SRS queue.
 *
 * The question itself is selected using the normal question
 * order. FSRS does not determine which completely new card
 * is introduced; FSRS determines its scheduling after it
 * has been reviewed.
 *
 * @returns {number|null} Added question index, or null.
 */
function addNewSRSQuestion() {
  const queue = state.questionSRSQueue;

  if (queue.length >= state.srsQueueSize) {
    return null;
  }

  const active = new Set(queue.map(({ index }) => index));

  const index = state.questionOrder.find(
    (questionIndex) => !cards.has(questionIndex) && !active.has(questionIndex),
  );

  if (index === undefined) {
    return null;
  }

  const card = fsrsModule.createEmptyCard();

  cards.set(index, card);

  queue.push({
    index,
    card,
  });

  return index;
}

/**
 * Fills one available position in the active SRS queue.
 *
 * @returns {number|null} Added question index, or null.
 */
function addNextSRSQuestion() {
  return addNewSRSQuestion();
}

/**
 * Initializes the SRS scheduler and restores persisted cards.
 *
 * Existing cards retain their FSRS state. Active cards are
 * restored into the current queue, while inactive cards remain
 * available to be reintroduced when their FSRS due date arrives.
 *
 * @param {string} quizStorageKey
 * @param {number} currentQuestionIndex
 * @returns {Promise<boolean>}
 */
export async function initSRS(quizStorageKey, currentQuestionIndex) {
  if (!(await loadFSRS())) {
    return false;
  }

  history.length = 0;
  cards.clear();
  state.questionSRSQueue = [];

  const savedState = loadQuestionSRSState(quizStorageKey);

  if (savedState) {
    const validIndices = new Set(state.questionOrder);

    for (const item of savedState.queue) {
      if (
        !validIndices.has(item.index) ||
        !item.card ||
        cards.has(item.index)
      ) {
        continue;
      }

      const card = restoreCard(item.card);

      cards.set(item.index, card);

      if (
        item.active !== false &&
        state.questionSRSQueue.length < state.srsQueueSize
      ) {
        state.questionSRSQueue.push({
          index: item.index,
          card,
        });
      }
    }
  }

  /*
   * If there was no saved SRS state, start with the
   * currently displayed question.
   */
  if (!savedState && state.questionOrder.includes(currentQuestionIndex)) {
    const card = fsrsModule.createEmptyCard();

    cards.set(currentQuestionIndex, card);

    state.questionSRSQueue.push({
      index: currentQuestionIndex,
      card,
    });
  }

  /*
   * Fill the initial queue.
   *
   * This is only a session queue-size rule. It does not
   * modify FSRS scheduling.
   */
  const initialSize = Math.min(state.srsQueueSize, state.questionOrder.length);

  while (state.questionSRSQueue.length < initialSize) {
    if (addNextSRSQuestion() === null) {
      break;
    }
  }

  sortSRSQueue();
  saveSRS(quizStorageKey);

  return true;
}

/**
 * Gets the next active SRS question.
 *
 * @returns {number|null}
 */
export function nextSRSQuestion() {
  return state.questionSRSQueue[0]?.index ?? null;
}

/**
 * Applies an FSRS rating to the current question.
 *
 * After FSRS calculates the new card:
 *
 * - Cards still in Learning or Relearning remain active.
 * - Cards that reach Review are removed from the current
 *   session queue.
 *
 *
 * @param {"Again"|"Hard"|"Good"|"Easy"} rating
 * @param {string} quizStorageKey
 * @returns {Promise<boolean>}
 */
export async function updateSRS(rating, quizStorageKey) {
  if (!VALID_RATINGS.has(rating)) {
    return false;
  }

  await loadFSRS();

  const queue = state.questionSRSQueue;

  if (!queue?.length) {
    return false;
  }

  const questionIndex = state.currentQuestionIndex;

  const position = queue.findIndex(({ index }) => index === questionIndex);

  if (position === -1) {
    return false;
  }

  const item = queue[position];

  const previousQueue = queue.map(({ index }) => index);

  const fsrsRating = fsrsModule.Rating[rating];

  const result = scheduler.next(item.card, new Date(), fsrsRating);

  item.card = result.card;

  cards.set(questionIndex, result.card);

  const change = {
    questionIndex,
    reviewLog: result.log,
    previousQueue,
    addedIndices: [],
    quizStorageKey,
  };

  // Consider cards that are no longer in Review state to be done
  if (result.card.state === fsrsModule.State.Review) {
    queue.splice(position, 1);

    const addedIndex = addNewSRSQuestion();

    if (addedIndex !== null) {
      change.addedIndices.push(addedIndex);
    }
  }

  sortSRSQueue();

  history.push(change);

  saveSRS(quizStorageKey);

  return true;
}

/**
 * Reverts the most recent SRS update.
 *
 * This restores the previous FSRS card state and the
 * previous active queue.
 *
 * @param {string} quizStorageKey
 * @returns {number|null} Reverted question index, or null.
 */
export function prevSRSQuestion(quizStorageKey) {
  const change = history.at(-1);

  if (!change) {
    return null;
  }

  if (change.quizStorageKey !== quizStorageKey) {
    return null;
  }

  history.pop();

  // Remove cards that were introduced only by the
  // reverted update.
  for (const index of change.addedIndices) {
    cards.delete(index);
  }

  // Roll the reviewed card back through FSRS.
  const card = cards.get(change.questionIndex);

  if (card) {
    const previousCard = scheduler.rollback(card, change.reviewLog);

    cards.set(change.questionIndex, previousCard);
  }

  /*
   * Restore the exact active queue from before
   * the rating was applied.
   */
  state.questionSRSQueue = change.previousQueue
    .map((index) => {
      const card = cards.get(index);

      if (!card) {
        return null;
      }

      return {
        index,
        card,
      };
    })
    .filter(Boolean);

  sortSRSQueue();
  saveSRS(quizStorageKey);

  return change.questionIndex;
}

/**
 * Clears the runtime undo history.
 *
 * Persisted FSRS card state is not deleted.
 *
 * @returns {void}
 */
export function clearSRSHistory() {
  history.length = 0;
}

export function getSRSCounts() {
  const total = state.questionOrder.length;

  // Cards not yet seen
  const due = state.questionOrder.filter((index) => {
    const card = cards.get(index);
    return !card?.last_review;
  }).length;

  // Cards seen that need reviewing
  const reviewing = state.questionSRSQueue.filter(({ card }) => {
    return card.last_review;
  }).length;

  // Cards that won't show up again
  const completed = total - due - reviewing;

  return {
    due,
    reviewing,
    completed,
  };
}

export function getSRSCurrentCategory() {
  const currentIndex = state.currentQuestionIndex;
  const card = cards.get(currentIndex);

  if (!card?.last_review) {
    return "due";
  }

  const isInQueue = state.questionSRSQueue.some(
    ({ index }) => index === currentIndex,
  );

  return isInQueue ? "reviewing" : "completed";
}
