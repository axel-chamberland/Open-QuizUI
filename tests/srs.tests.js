import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./state.js", () => ({
  state: {
    srsLevel: 3,
  },
}));

vi.mock("./persistence/question_order.js", () => ({
  saveQuestionSRSOrder: vi.fn(),
}));

import {
  buildQuestionSRSOrder,
  clearSRSHistory,
  nextSRSQuestion,
  prevSRSQuestion,
  startSRS,
  updateSRS,
} from "./srs.js";

import { saveQuestionSRSOrder } from "./persistence/question_order.js";

function createItems(levels) {
  return levels.map((level, index) => ({
    index,
    level,
  }));
}

describe("buildQuestionSRSOrder", () => {
  it("orders questions by ascending level", () => {
    const items = createItems([2, 0, 1, 0]);

    const result = buildQuestionSRSOrder(items);

    expect(result.map((item) => item.index)).toEqual([1, 3, 2, 0]);
  });

  it("uses index as the tie-breaker", () => {
    const items = [
      { index: 3, level: 1 },
      { index: 1, level: 1 },
      { index: 2, level: 1 },
    ];

    const result = buildQuestionSRSOrder(items);

    expect(result.map((item) => item.index)).toEqual([1, 2, 3]);
  });
});

describe("SRS session", () => {
  beforeEach(() => {
    clearSRSHistory();
    saveQuestionSRSOrder.mockClear();
  });

  it("starts with the lowest-level question", () => {
    const items = createItems([2, 0, 1]);

    startSRS(items);

    expect(nextSRSQuestion()).toBe(1);
  });

  it("nextSRSQuestion peeks without removing the item", () => {
    const items = createItems([0, 1]);

    startSRS(items);

    expect(nextSRSQuestion()).toBe(0);
    expect(nextSRSQuestion()).toBe(0);
  });

  it("correct answer increases the level", () => {
    const items = createItems([0, 1]);

    startSRS(items);

    expect(nextSRSQuestion()).toBe(0);

    updateSRS(true, items, "quiz");

    expect(items[0].level).toBe(1);
  });

  it("correct answer reorders the queue", () => {
    const items = createItems([0, 1]);

    startSRS(items);

    expect(nextSRSQuestion()).toBe(0);

    updateSRS(true, items, "quiz");

    expect(nextSRSQuestion()).toBe(1);
  });

  it("wrong answer resets the level to zero", () => {
    const items = createItems([2, 0]);

    startSRS(items);

    expect(nextSRSQuestion()).toBe(1);

    updateSRS(true, items, "quiz");

    expect(items[1].level).toBe(1);

    updateSRS(false, items, "quiz");

    expect(items[1].level).toBe(0);
  });

  it("wrong answer gives the item highest priority again", () => {
    const items = createItems([1, 0]);

    startSRS(items);

    expect(nextSRSQuestion()).toBe(1);

    updateSRS(true, items, "quiz");

    expect(nextSRSQuestion()).toBe(0);

    updateSRS(false, items, "quiz");

    expect(nextSRSQuestion()).toBe(0);
  });

  it("removes an item when it reaches the threshold", () => {
    const items = createItems([2, 0]);

    startSRS(items);

    expect(nextSRSQuestion()).toBe(1);

    updateSRS(true, items, "quiz");
    updateSRS(true, items, "quiz");
    updateSRS(true, items, "quiz");

    expect(items[1].level).toBe(3);
    expect(nextSRSQuestion()).toBe(0);
  });

  it("does not remove an item below the threshold", () => {
    const items = createItems([0, 1]);

    startSRS(items);

    updateSRS(true, items, "quiz");

    expect(items[0].level).toBe(1);
    expect(nextSRSQuestion()).toBe(1);
  });

  it("returns null when all questions have been removed", () => {
    const items = createItems([0]);

    startSRS(items);

    updateSRS(true, items, "quiz");
    updateSRS(true, items, "quiz");
    updateSRS(true, items, "quiz");

    expect(nextSRSQuestion()).toBeNull();
  });

  it("undoes a level increase", () => {
    const items = createItems([0, 1]);

    startSRS(items);

    expect(nextSRSQuestion()).toBe(0);

    updateSRS(true, items, "quiz");

    expect(items[0].level).toBe(1);

    const index = prevSRSQuestion(items, "quiz");

    expect(index).toBe(0);
    expect(items[0].level).toBe(0);
  });

  it("undoes a wrong answer", () => {
    const items = createItems([0, 1]);

    startSRS(items);

    updateSRS(true, items, "quiz");
    updateSRS(false, items, "quiz");

    expect(items[0].level).toBe(0);

    prevSRSQuestion(items, "quiz");

    expect(items[0].level).toBe(1);
    expect(nextSRSQuestion()).toBe(0);
  });

  it("restores an item removed by the threshold", () => {
    const items = createItems([0]);

    startSRS(items);

    updateSRS(true, items, "quiz");
    updateSRS(true, items, "quiz");
    updateSRS(true, items, "quiz");

    expect(nextSRSQuestion()).toBeNull();

    const index = prevSRSQuestion(items, "quiz");

    expect(index).toBe(0);
    expect(items[0].level).toBe(2);
    expect(nextSRSQuestion()).toBe(0);
  });

  it("saves after an SRS update", () => {
    const items = createItems([0]);

    startSRS(items);

    updateSRS(true, items, "quiz");

    expect(saveQuestionSRSOrder).toHaveBeenCalledWith("quiz", items);
  });

  it("saves after undo", () => {
    const items = createItems([0]);

    startSRS(items);

    updateSRS(true, items, "quiz");
    saveQuestionSRSOrder.mockClear();

    prevSRSQuestion(items, "quiz");

    expect(saveQuestionSRSOrder).toHaveBeenCalledWith("quiz", items);
  });
});

describe("SRS edge cases", () => {
  beforeEach(() => {
    clearSRSHistory();
  });

  it("updateSRS fails when SRS has not started", () => {
    const items = createItems([0]);

    expect(updateSRS(true, items, "quiz")).toBe(false);
  });

  it("prevSRSQuestion returns null with no history", () => {
    const items = createItems([0]);

    startSRS(items);

    expect(prevSRSQuestion(items, "quiz")).toBeNull();
  });

  it("clearSRSHistory clears the queue", () => {
    const items = createItems([0]);

    startSRS(items);
    clearSRSHistory();

    expect(nextSRSQuestion()).toBeNull();
  });
});
