/**
 * @vitest-environment jsdom
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

/*
 * srs.js loads ts-fsrs from a CDN, which no test can reach. The mock
 * stands in for it with a scheduler that is easy to reason about:
 * a card reaches Review after two ratings that are not Again - that is
 * the moment srs.js takes it out of the session queue - and Again
 * sends it back to Relearning. rollback() restores the card exactly as
 * it was before the rating, as ts-fsrs does.
 */
vi.mock("https://cdn.jsdelivr.net/npm/ts-fsrs@5.4.2/+esm", () => {
  const Rating = { Again: 1, Hard: 2, Good: 3, Easy: 4 };
  const State = { New: 0, Learning: 1, Review: 2, Relearning: 3 };
  const REVIEW_AFTER = 2;

  return {
    Rating,
    State,
    createEmptyCard: () => ({
      state: State.New,
      reps: 0,
      due: new Date(0),
      last_review: undefined,
    }),
    fsrs: () => ({
      next(card, now, rating) {
        const passed = rating >= Rating.Hard;
        const reps = passed ? (card.reps ?? 0) + 1 : 0;

        return {
          card: {
            ...card,
            reps,
            state: !passed
              ? State.Relearning
              : reps >= REVIEW_AFTER
                ? State.Review
                : State.Learning,
            due: new Date(now.getTime() + 1000),
            last_review: now,
          },
          log: { card: { ...card }, rating, review: now },
        };
      },
      rollback(card, log) {
        return { ...log.card };
      },
    }),
  };
});

import { state } from "../frontend/src/state.js";
import { loadQuestionSRSState } from "../frontend/src/persistence/question_order.js";
import {
  clearSRSHistory,
  getSRSCounts,
  getSRSCurrentCategory,
  initSRS,
  nextSRSQuestion,
  prevSRSQuestion,
  removeQuestionFromSRS,
  setSRSConfig,
  updateSRS,
} from "../frontend/src/srs.js";

const QUIZ_KEY = "quiz";

/**
 * Starts a session over a quiz of `questions` questions.
 *
 * @param {object} [options]
 * @returns {Promise<boolean>} Whatever initSRS returned.
 */
function startSession({ questions = 3, queueSize = 3, current = 0 } = {}) {
  state.questionOrder = Array.from({ length: questions }, (_, index) => index);
  state.srsQueueSize = queueSize;
  state.currentQuestionIndex = current;
  state.quizStorageKey = QUIZ_KEY;

  return initSRS(QUIZ_KEY, current);
}

function queueIndexes() {
  return state.questionSRSQueue.map(({ index }) => index);
}

function savedIndexes() {
  return loadQuestionSRSState(QUIZ_KEY).queue.map(({ index }) => index);
}

/**
 * Rates the card in view until it reaches Review, which is where
 * srs.js takes it out of the queue.
 *
 * @returns {Promise<void>}
 */
async function finishCard() {
  await updateSRS("Good", QUIZ_KEY);
  await updateSRS("Good", QUIZ_KEY);
}

beforeEach(() => {
  localStorage.clear();

  clearSRSHistory();

  state.questionOrder = [];
  state.questionSRSQueue = [];
  state.currentQuestionIndex = 0;
  state.quizStorageKey = QUIZ_KEY;
});

describe("initSRS", () => {
  it("fills the queue from the question order", async () => {
    expect(await startSession({ questions: 4, queueSize: 2 })).toBe(true);

    expect(queueIndexes()).toEqual([0, 1]);
  });

  it("never queues the same question twice", async () => {
    await startSession({ questions: 3, queueSize: 3 });

    expect(queueIndexes()).toEqual([0, 1, 2]);
  });

  it("starts with the question in view when the queue is small", async () => {
    await startSession({ questions: 3, queueSize: 1, current: 2 });

    expect(queueIndexes()).toEqual([2]);
  });

  it("restores the queue that was saved last time", async () => {
    await startSession({ questions: 3, queueSize: 3 });
    await finishCard();

    expect(savedIndexes()).toEqual([0, 1, 2]);

    await initSRS(QUIZ_KEY, 1);

    // The reviewed card is scheduled ahead, so it is not queued again.
    expect(queueIndexes()).toEqual([1, 2]);
  });

  it("drops a saved card the quiz no longer has", async () => {
    localStorage.setItem(
      `questionSRSQueue_${QUIZ_KEY}`,
      JSON.stringify({
        queue: [
          {
            index: 0,
            card: { state: 1, reps: 1, due: new Date(0).toISOString() },
            active: true,
          },
          {
            index: 9,
            card: { state: 1, reps: 1, due: new Date(0).toISOString() },
            active: true,
          },
        ],
      }),
    );

    await startSession({ questions: 2, queueSize: 2 });

    expect(queueIndexes()).toEqual([0, 1]);
  });
});

describe("nextSRSQuestion", () => {
  it("returns the first card without taking it out of the queue", async () => {
    await startSession({ questions: 2, queueSize: 2 });

    expect(nextSRSQuestion()).toBe(0);
    expect(nextSRSQuestion()).toBe(0);
  });

  it("returns null when the queue is empty", async () => {
    await startSession({ questions: 1, queueSize: 1 });
    await finishCard();

    expect(nextSRSQuestion()).toBeNull();
  });
});

describe("updateSRS", () => {
  it("refuses a rating that is not one of the four", async () => {
    await startSession({ questions: 2, queueSize: 2 });

    expect(await updateSRS("Nope", QUIZ_KEY)).toBe(false);
  });

  it("refuses a rating before a session is started", async () => {
    expect(await updateSRS("Good", QUIZ_KEY)).toBe(false);
  });

  it("refuses a rating for a question that is not in the queue", async () => {
    await startSession({ questions: 2, queueSize: 1 });

    state.currentQuestionIndex = 1;

    expect(await updateSRS("Good", QUIZ_KEY)).toBe(false);
  });

  it("keeps a card that is still learning in the queue", async () => {
    await startSession({ questions: 2, queueSize: 2 });

    await updateSRS("Good", QUIZ_KEY);

    // The reviewed card is due later than the one that is up next.
    expect(queueIndexes()).toEqual([1, 0]);
  });

  it("keeps a card rated Again in the queue", async () => {
    await startSession({ questions: 2, queueSize: 2 });

    await updateSRS("Again", QUIZ_KEY);

    expect(queueIndexes()).toContain(0);
  });

  it("takes a reviewed card out and pulls the next question in", async () => {
    await startSession({ questions: 3, queueSize: 2 });

    await finishCard();

    expect(queueIndexes()).toEqual([1, 2]);
  });

  it("saves the queue with the cards that are still active", async () => {
    await startSession({ questions: 3, queueSize: 3 });

    await finishCard();

    const saved = loadQuestionSRSState(QUIZ_KEY);

    expect(saved.queue).toEqual([
      { index: 0, card: expect.any(Object), active: false },
      { index: 1, card: expect.any(Object), active: true },
      { index: 2, card: expect.any(Object), active: true },
    ]);
  });
});

describe("prevSRSQuestion", () => {
  it("returns null when there is nothing to undo", async () => {
    await startSession({ questions: 2, queueSize: 2 });

    expect(prevSRSQuestion(QUIZ_KEY)).toBeNull();
  });

  it("returns null for another quiz's session", async () => {
    await startSession({ questions: 2, queueSize: 2 });
    await updateSRS("Good", QUIZ_KEY);

    expect(prevSRSQuestion("another-quiz")).toBeNull();
  });

  it("puts the reviewed card back in the queue", async () => {
    await startSession({ questions: 3, queueSize: 2 });
    await finishCard();

    expect(queueIndexes()).toEqual([1, 2]);

    expect(prevSRSQuestion(QUIZ_KEY)).toBe(0);

    // The card is due again from its first rating, so it sorts behind
    // the untouched card, which is still due from the start.
    expect(queueIndexes()).toEqual([1, 0]);
  });

  it("drops the question the undone rating pulled in", async () => {
    await startSession({ questions: 3, queueSize: 2 });
    await finishCard();

    expect(savedIndexes()).toEqual([0, 1, 2]);

    prevSRSQuestion(QUIZ_KEY);

    expect(savedIndexes()).toEqual([0, 1]);
  });

  it("rolls the card's schedule back", async () => {
    await startSession({ questions: 2, queueSize: 2 });

    await updateSRS("Good", QUIZ_KEY);

    const before = loadQuestionSRSState(QUIZ_KEY).queue.find(
      ({ index }) => index === 0,
    ).card;

    await updateSRS("Good", QUIZ_KEY);
    prevSRSQuestion(QUIZ_KEY);

    const after = loadQuestionSRSState(QUIZ_KEY).queue.find(
      ({ index }) => index === 0,
    ).card;

    expect(after).toEqual(before);
  });
});

describe("clearSRSHistory", () => {
  it("leaves nothing to undo", async () => {
    await startSession({ questions: 2, queueSize: 2 });
    await updateSRS("Good", QUIZ_KEY);

    clearSRSHistory();

    expect(prevSRSQuestion(QUIZ_KEY)).toBeNull();
  });
});

describe("removeQuestionFromSRS", () => {
  it("drops the question and shifts the ones behind it", async () => {
    await startSession({ questions: 3, queueSize: 3 });

    removeQuestionFromSRS(1);

    expect(queueIndexes()).toEqual([0, 1]);
    expect(savedIndexes()).toEqual([0, 1]);
  });

  it("keeps the indexes of the questions behind when they did not move", async () => {
    await startSession({ questions: 3, queueSize: 3 });

    removeQuestionFromSRS(1, false);

    expect(queueIndexes()).toEqual([0, 2]);
    expect(savedIndexes()).toEqual([0, 2]);
  });
});

describe("getSRSCounts", () => {
  it("counts the cards that are new, in review and done", async () => {
    await startSession({ questions: 3, queueSize: 3 });

    expect(getSRSCounts()).toEqual({ due: 3, reviewing: 0, completed: 0 });

    await updateSRS("Good", QUIZ_KEY);

    expect(getSRSCounts()).toEqual({ due: 2, reviewing: 1, completed: 0 });

    await updateSRS("Good", QUIZ_KEY);

    expect(getSRSCounts()).toEqual({ due: 2, reviewing: 0, completed: 1 });
  });
});

describe("getSRSCurrentCategory", () => {
  it("reports where the question in view belongs", async () => {
    await startSession({ questions: 2, queueSize: 2 });

    expect(getSRSCurrentCategory()).toBe("due");

    await finishCard();

    expect(getSRSCurrentCategory()).toBe("completed");

    state.currentQuestionIndex = 1;
    await updateSRS("Good", QUIZ_KEY);

    expect(getSRSCurrentCategory()).toBe("reviewing");
  });
});

describe("setSRSConfig", () => {
  it("applies the settings to the session", async () => {
    await startSession({ questions: 1, queueSize: 1 });

    setSRSConfig({ request_retention: 0.8, enable_fuzz: false });

    expect(state.srsConfig.request_retention).toBe(0.8);
    expect(state.srsConfig.enable_fuzz).toBe(false);
    expect(state.srsConfig.maximum_interval).toBe(365);
  });
});
