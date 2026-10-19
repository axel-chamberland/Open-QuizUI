import { state } from "../state.js";
import { saveQuestionOrder } from "../persistence/question_order.js";
import {
  addQuestion,
  deleteQuestion,
  goTo,
  removeAddedQuestion,
  updateQuestionCounts,
  updateQuestionNumbers,
} from "../quiz.js";
import {
  hasUnsavedEditorChanges,
  openEditor,
  updateEditorQuestionNumber,
} from "./editor.js";
import { showAlert, showPrompt } from "../ui/alert.js";

let workingOrder = null;
let originalOrder = null;
let dragIndex = null;
let keyHandler = null;

/**
 * Question indexes added while the editor is open.
 *
 * Added questions are saved to the browser the moment they are
 * created, so canceling the editor has to remove them explicitly to
 * leave the quiz as the user found it.
 */
let sessionAddedIndexes = [];

/**
 * Question indexes the user actually dragged during this editor
 * session. Rows that merely shifted because a neighbour moved past
 * them are marked differently, so the two cases can be told apart.
 */
const draggedItems = new Set();

/**
 * Tears down the touch drag currently in progress, if any, so a new
 * drag (or closing the editor) can always cancel the previous one and
 * no handler can outlive its gesture.
 */
let dragCancel = null;

/**
 * Auto-scroll and last pointer position of the mouse drag in progress,
 * if any.
 *
 * The native drag reports the pointer only when it moves, so a drag
 * held past the list stopped scrolling the moment the mouse did (the
 * browser's own auto-scroll has the same flaw, which is why most apps
 * jerk their way down a list). The position is remembered instead and
 * the scroll runs in animation frames; see createDragAutoScroll.
 */
let mouseDragScroll = null;
let mouseDragY = null;

/**
 * Pointer type of the most recent pointer down, so a native HTML5
 * drag (mouse only) can be told apart from touch.
 */
let lastPointerType = "mouse";

document.addEventListener(
  "pointerdown",
  (event) => {
    lastPointerType = event.pointerType;
  },
  true,
);

/*
 * The mouse drag's own drag events, on the document rather than on the
 * rows: the rows are rebuilt when a drop lands, and the drag outlives
 * them. They also stand in for the browser's drop target feedback,
 * which cannot keep up while the list scrolls under a still pointer.
 */
document.addEventListener(
  "dragover",
  (event) => {
    if (mouseDragScroll === null) {
      return;
    }

    // Everything accepts the drop, so a row can be dropped past the
    // list - the very place the auto-scroll happens.
    event.preventDefault();

    mouseDragY = event.clientY;

    mouseDragScroll.track(mouseDragY);

    highlightSlotUnderPointer(mouseDragY);
  },
  true,
);

document.addEventListener(
  "drop",
  (event) => {
    if (mouseDragScroll === null) {
      return;
    }

    event.preventDefault();

    dropMouseDrag(event.clientY ?? mouseDragY);
  },
  true,
);

document.addEventListener(
  "dragend",
  () => {
    if (mouseDragScroll !== null) {
      stopMouseDrag();
    }
  },
  true,
);

/**
 * Returns a single-line plain-text snippet of a question, for the
 * question order list.
 *
 * @param {number} questionIndex Index in quiz.questions.
 * @returns {string} Truncated plain-text question.
 */
function getQuestionSnippet(questionIndex) {
  const question = state.quiz.questions[questionIndex];

  if (!question) {
    return "(empty question)";
  }

  const scratch = document.createElement("div");

  scratch.innerHTML = question.question || "";

  const text = scratch.textContent.trim();

  if (text === "") {
    return "(empty question)";
  }

  return text.length > 60 ? `${text.slice(0, 60)}…` : text;
}

/**
 * Opens the question order editor overlay.
 *
 * Starts from the current navigation order; changes are staged until
 * saved. Rows whose position differs from the order the editor was
 * opened with are color coded.
 *
 * @returns {void}
 */
export function openOrderEditor() {
  // Never inherit a drag from a previous session.
  dragCancel?.();
  stopMouseDrag();

  originalOrder = state.questionOrder.slice();
  workingOrder = state.questionOrder.slice();

  // Questions added from a previous session belong to the quiz now.
  sessionAddedIndexes = [];

  draggedItems.clear();
  document.getElementById("order-editor").classList.remove("dragging");

  buildOrderList();

  keyHandler = (e) => {
    if (e.key !== "Escape") {
      return;
    }

    /*
     * A prompt opened from the overlay (adding or cancelling a
     * question) owns the keyboard while it is up.
     */
    if (
      document.getElementById("global-prompt").classList.contains("visible")
    ) {
      return;
    }

    e.preventDefault();
    e.stopPropagation();
    cancelOrderEditor();
  };

  document.addEventListener("keydown", keyHandler, true);

  document.getElementById("order-editor").classList.add("visible");

  // Start the user off on the row the buttons act on.
  queryRow(state.currentQuestionIndex)?.scrollIntoView({ block: "nearest" });
}

/**
 * Looks up a question's row in the staged list.
 *
 * @param {number} questionIndex Question index.
 * @returns {HTMLElement|null} The row, or null when it is not listed.
 */
function queryRow(questionIndex) {
  return document
    .getElementById("order-editor-list")
    .querySelector(`.order-row[data-question-index="${questionIndex}"]`);
}

/**
 * Makes a question the one the editor is on.
 *
 * The buttons in the list and the editor's own question number both
 * act on this question, so picking a row moves the editor - and the
 * quiz page behind it - to that question. Unsaved changes in the
 * editor are asked about first, since they are left in its fields.
 *
 * @param {number} questionIndex Question index to switch to.
 * @returns {void}
 */
function selectQuestion(questionIndex) {
  if (questionIndex === state.currentQuestionIndex) {
    return;
  }

  const switchQuestion = () => {
    state.currentQuestionIndex = questionIndex;

    goTo(questionIndex);
    openEditor();

    // Move the marker with the editor.
    buildOrderList();
  };

  if (!hasUnsavedEditorChanges()) {
    switchQuestion();
    return;
  }

  showPrompt(
    `Switch to question ${state.questionOrder.indexOf(questionIndex) + 1}?\nUnsaved changes to the current question will be lost.`,
    switchQuestion,
    null,
    "yes",
    "no",
  );
}

/**
 * Closes the order editor overlay.
 *
 * The editor calls this as it is closed, since the list is not modal
 * and would otherwise be left up over the quiz page.
 *
 * @returns {void}
 */
export function closeOrderEditor() {
  // Never leave a half-finished drag behind: it would keep its
  // listeners attached and break the next time the editor is used.
  dragCancel?.();
  stopMouseDrag();

  sessionAddedIndexes = [];

  document.getElementById("order-editor").classList.remove("visible");
  document.removeEventListener("keydown", keyHandler, true);
  keyHandler = null;
}

/**
 * Cancels the order editor, asking first when questions were added.
 *
 * Added questions are saved the moment they are created (they are real
 * edits), so cancelling has to remove them again to leave the quiz as
 * it was found.
 *
 * @returns {void}
 */
function cancelOrderEditor() {
  if (sessionAddedIndexes.length === 0) {
    closeOrderEditor();
    return;
  }

  const added = sessionAddedIndexes.length;

  showPrompt(
    added === 1
      ? "Cancel? The question you added will be removed again."
      : `Cancel? The ${added} questions you added will be removed again.`,
    () => {
      rollBackAddedQuestions();
      closeOrderEditor();
    },
    null,
    "yes",
    "no",
  );
}

/**
 * Removes the questions added since the editor was opened.
 *
 * They are removed from the highest index down, because removing a
 * question shifts the indexes after it.
 *
 * @returns {void}
 */
function rollBackAddedQuestions() {
  const editedWasAdded = sessionAddedIndexes.includes(
    state.currentQuestionIndex,
  );

  for (const index of [...sessionAddedIndexes].sort((a, b) => b - a)) {
    removeAddedQuestion(index);
  }

  sessionAddedIndexes = [];

  originalOrder = state.questionOrder.slice();
  workingOrder = state.questionOrder.slice();

  if (editedWasAdded) {
    /*
     * The question the editor was showing is gone, and so is whatever
     * was typed into its fields: send the editor back to the last
     * question that is left.
     */
    state.currentQuestionIndex = state.quiz.questions.length - 1;

    goTo(state.currentQuestionIndex);
    openEditor();

    return;
  }

  // The count went down, and the edited question is one of the quiz's
  // own, so its index did not move.
  updateEditorQuestionNumber();
}

/**
 * Adds a blank question to the quiz from the question list.
 *
 * The question is saved immediately and placed in the list next to the
 * question that is picked - or at the end of it. It does not become
 * the picked one: tapping its row is what moves the editor to it.
 *
 * @param {"before"|"after"|"end"} where Where the question goes
 *   relative to the current one.
 * @returns {void}
 */
function addOrderQuestion(where = "end") {
  const savedPosition = state.questionOrder.indexOf(state.currentQuestionIndex);
  const listPosition = workingOrder.indexOf(state.currentQuestionIndex);

  /*
   * The question is appended to the quiz either way, so it can only be
   * placed next to the current one through the navigation order.
   */
  let orderPosition = null;

  if (where !== "end" && savedPosition !== -1) {
    orderPosition = where === "before" ? savedPosition : savedPosition + 1;
  }

  const index = addQuestion(orderPosition);

  sessionAddedIndexes.push(index);

  // Stage the new row where the user asked for it.
  let stagedPosition = workingOrder.length;

  if (where !== "end" && listPosition !== -1) {
    stagedPosition = where === "before" ? listPosition : listPosition + 1;
  }

  workingOrder.splice(stagedPosition, 0, index);
  originalOrder.splice(stagedPosition, 0, index);

  buildOrderList();

  queryRow(index)?.scrollIntoView({ block: "nearest" });

  /*
   * The added question is saved right away, so the count - and, for a
   * question placed in front of the current one, the position - has
   * changed for good.
   */
  updateEditorQuestionNumber();
}

/**
 * Deletes the question that is picked in the list.
 *
 * The row that is picked is marked, so the button always has an
 * unambiguous target. Unlike a reorder, a deletion is saved right away.
 *
 * @returns {void}
 */
function deleteCurrentQuestion() {
  const index = state.currentQuestionIndex;
  const position = Math.max(0, workingOrder.indexOf(index));

  // Whatever is deleted, the quiz keeps at least one question.
  if (state.questionOrder.length <= 1) {
    showAlert("A quiz needs at least one question.");
    return;
  }

  showPrompt(
    "Delete the current question?\nIt will be removed from the quiz.",
    () => {
      /*
       * A question added in the editor is taken out of the quiz array,
       * which moves the indexes behind it down; one of the quiz's own
       * questions keeps its index and is marked as deleted.
       */
      const shifted = index >= state.builtInQuestionCount;

      deleteQuestion(index);

      dropFromStagedOrders(index, shifted);

      /*
       * Leave the editor on the question that took its place: the next
       * one in the list, or the last question when the deleted one was
       * at the end.
       */
      const nextIndex =
        workingOrder[Math.min(position, workingOrder.length - 1)];

      state.currentQuestionIndex = nextIndex;

      goTo(nextIndex);
      openEditor();

      buildOrderList();
    },
    null,
    "yes",
    "no",
  );
}

/**
 * Drops a question from the order staged by the overlay.
 *
 * The staged order has to follow what deleting the question did to the
 * quiz: a question added in the editor moves the indexes behind it
 * down, while one of the quiz's own questions leaves them alone.
 *
 * @param {number} index Deleted question index.
 * @param {boolean} shifted Whether the indexes behind it moved down.
 * @returns {void}
 */
function dropFromStagedOrders(index, shifted) {
  const drop = (order) =>
    order
      .filter((item) => item !== index)
      .map((item) => (shifted && item > index ? item - 1 : item));

  workingOrder = drop(workingOrder);
  originalOrder = drop(originalOrder);
}

/**
 * Saves the staged order, updates the runtime state and closes.
 *
 * @returns {void}
 */
function saveOrder() {
  if (JSON.stringify(workingOrder) !== JSON.stringify(originalOrder)) {
    state.questionOrder = workingOrder.slice();

    saveQuestionOrder(state.quizStorageKey, state.questionOrder);

    updateQuestionNumbers();
    updateQuestionCounts();

    // The saved order is what the editor's question number reads.
    updateEditorQuestionNumber();
  }

  closeOrderEditor();
}

/**
 * Starts a touch/pen drag from a row's grip handle.
 *
 * The handle owns its gesture (touch-action: none), so the drag arms
 * immediately and the browser cannot steal it with a scroll. All
 * listeners live on `document` and filter on the pointer id, so the
 * drag always receives its end event - even if the finger leaves the
 * list - and can therefore never leak.
 *
 * @param {PointerEvent} event Pointer down on a grip handle.
 * @param {number} position Row position at pointer down.
 */
function startGripDrag(event, position) {
  // A previous drag that never ended must not keep its listeners.
  dragCancel?.();

  const list = document.getElementById("order-editor-list");
  const overlay = document.getElementById("order-editor");
  const pointerId = event.pointerId;
  const row = list.querySelectorAll(".order-row")[position];

  let done = false;

  /*
   * The scroll is driven by animation frames rather than by pointer
   * events: a finger held still sends none, and that is exactly when
   * the list has to keep scrolling.
   */
  const scroll = createDragAutoScroll(handlePointerDragOver);

  const cleanup = () => {
    if (done) {
      return;
    }

    done = true;

    scroll.stop();

    overlay.classList.remove("dragging");
    document.removeEventListener("pointermove", onMove);
    document.removeEventListener("pointerup", onUp);
    document.removeEventListener("pointercancel", onUp);
    document.removeEventListener("pointerdown", onOtherPointer, true);

    /*
     * No rebuild here: the rows were updated in place while dragging,
     * and rebuilding would destroy the element the finger is on (and
     * with it the implicit pointer capture) right when it is released.
     */
    if (row) {
      row.classList.remove("order-dragging");
    }

    dragIndex = null;

    if (dragCancel === cleanup) {
      dragCancel = null;
    }
  };

  const onMove = (moveEvent) => {
    if (moveEvent.pointerId !== pointerId) {
      return;
    }

    moveEvent.preventDefault();

    scroll.track(moveEvent.clientY);

    handlePointerDragOver(moveEvent.clientY);
  };

  const onUp = (upEvent) => {
    if (upEvent.pointerId === pointerId) {
      cleanup();
    }
  };

  // A second finger (a pinch, not the primary pointer) abandons the drag.
  const onOtherPointer = (downEvent) => {
    if (!downEvent.isPrimary) {
      cleanup();
    }
  };

  dragIndex = position;
  dragCancel = cleanup;

  overlay.classList.add("dragging");

  if (row) {
    row.classList.add("order-dragging");
  }

  document.addEventListener("pointermove", onMove);
  document.addEventListener("pointerup", onUp);
  document.addEventListener("pointercancel", onUp);
  document.addEventListener("pointerdown", onOtherPointer, true);
}

/**
 * Starts a mouse drag from a row: the native HTML5 drag.
 *
 * The row is only moved when the drop lands, so a drag abandoned with
 * Escape leaves the order as it was.
 *
 * @param {DragEvent} event Drag start event.
 * @param {number} position Row position at drag start.
 * @param {HTMLElement} row Row element that is being dragged.
 * @returns {void}
 */
function startMouseDrag(event, position, row) {
  // A previous drag that never ended must not keep its scroll running.
  stopMouseDrag();

  dragIndex = position;
  mouseDragY = event.clientY;

  row?.classList.add("order-dragging");

  mouseDragScroll = createDragAutoScroll(highlightSlotUnderPointer);
  mouseDragScroll.track(mouseDragY);
}

/**
 * Ends a mouse drag: stops its auto-scroll and clears the marks it put
 * on the list.
 *
 * @returns {void}
 */
function stopMouseDrag() {
  mouseDragScroll?.stop();

  mouseDragScroll = null;
  mouseDragY = null;
  dragIndex = null;

  document
    .querySelectorAll(
      "#order-editor-list .order-dragging, #order-editor-list .order-drop-target",
    )
    .forEach((row) => {
      row.classList.remove("order-dragging", "order-drop-target");
    });
}

/**
 * Drops the dragged row into the slot the pointer is over.
 *
 * The slot is taken from the pointer rather than from the row the
 * browser reports under it: the list scrolls on without the mouse, so
 * that row is stale by the time the drop arrives - and past the list it
 * is not a row at all.
 *
 * @param {number} pointerY Pointer client Y coordinate.
 * @returns {void}
 */
function dropMouseDrag(pointerY) {
  const from = dragIndex;
  const { rows, target } = slotUnderPointer(pointerY);

  stopMouseDrag();

  if (from === null || rows.length === 0 || from === target) {
    return;
  }

  const [item] = workingOrder.splice(from, 1);
  workingOrder.splice(target, 0, item);

  draggedItems.add(item);

  buildOrderList();
}

/**
 * Reorders the list so the dragged question sits at the position the
 * pointer is over.
 *
 * The rows are moved in place (never rebuilt): rebuilding the list
 * mid-drag destroys the element under the finger and with it the
 * browser's implicit pointer capture, which killed the drag.
 *
 * @param {number} pointerY Pointer client Y coordinate.
 */
function handlePointerDragOver(pointerY) {
  const list = document.getElementById("order-editor-list");
  const dragged = list.querySelector(".order-row.order-dragging");

  if (!dragged) {
    return;
  }

  const { rows, target } = slotUnderPointer(pointerY);
  const from = rows.indexOf(dragged);

  if (target === from) {
    return;
  }

  const reference = target > from ? rows[target].nextSibling : rows[target];

  list.insertBefore(dragged, reference);

  const [item] = workingOrder.splice(from, 1);
  workingOrder.splice(target, 0, item);

  draggedItems.add(Number(dragged.dataset.questionIndex));

  updateRowLabels();
}

/**
 * Resolves the slot the pointer is over: the first row whose midpoint is
 * below the pointer, or the end of the list when there is none.
 *
 * @param {number} pointerY Pointer client Y coordinate.
 * @returns {{rows: HTMLElement[], target: number}} Rows, and the slot.
 */
function slotUnderPointer(pointerY) {
  const list = document.getElementById("order-editor-list");
  const rows = Array.from(list.querySelectorAll(".order-row"));

  // The insertion point is the first row whose midpoint is below the
  // pointer; with no such row, the end of the list.
  let target = rows.length - 1;

  for (let index = 0; index < rows.length; index++) {
    const rect = rows[index].getBoundingClientRect();

    if (pointerY < rect.top + rect.height / 2) {
      target = index;
      break;
    }
  }

  return { rows, target };
}

/**
 * Marks the slot the pointer is over, for a drag that moves its row on
 * the drop rather than while dragging (the mouse one). The browser marks
 * that row itself, but not while the list scrolls under a still pointer.
 *
 * @param {number} pointerY Pointer client Y coordinate.
 * @returns {void}
 */
function highlightSlotUnderPointer(pointerY) {
  const { rows, target } = slotUnderPointer(pointerY);

  rows.forEach((row, index) => {
    row.classList.toggle(
      "order-drop-target",
      index === target && !row.classList.contains("order-dragging"),
    );
  });
}

/**
 * Runs a drag's auto-scroll in animation frames.
 *
 * The step is driven by frames rather than by the drag's own events: a
 * pointer that is held still sends none, which is exactly when the list
 * has to keep scrolling. It runs while the pointer is past the list, and
 * stops on its own once the list is at its end.
 *
 * @param {(pointerY: number) => void} [onScroll] Called after each
 *   scroll step to re-check what is under the pointer.
 * @returns {{track: (pointerY: number) => void, stop: () => void}} The
 *   scroll, fed the pointer position as it moves.
 */
function createDragAutoScroll(onScroll) {
  let frame = null;
  let pointerY = null;

  const step = () => {
    frame = null;

    if (pointerY === null || scrollListOutsidePointer(pointerY) === 0) {
      return;
    }

    // The scroll moved the list: re-check what is under the pointer.
    onScroll?.(pointerY);

    frame = requestAnimationFrame(step);
  };

  return {
    track(position) {
      pointerY = position;

      if (frame === null) {
        frame = requestAnimationFrame(step);
      }
    },
    stop() {
      if (frame !== null) {
        cancelAnimationFrame(frame);
      }

      frame = null;
      pointerY = null;
    },
  };
}

/**
 * Scrolls the order list while the pointer is dragged past its top or
 * bottom edge, and not at all while the pointer is over the list.
 *
 * Scrolling only outside the list is what keeps a long list from
 * fighting itself: an edge zone inside the list made the scroll
 * direction flip as rows were reordered under the pointer, and the
 * list lurched up and down.
 *
 * The step grows with the distance past the edge - roughly linear up
 * close, then accelerating - so a slot can still be nudged by a row or
 * two near the edge, while a very long list (imagine 1000 questions)
 * is crossed quickly by pulling the finger well past it. The cap
 * scales with the list length: a short list cannot be flung around,
 * and even a huge one is traversed in well under a second at full
 * stretch.
 *
 * @param {number} pointerY Pointer client Y coordinate.
 * @returns {number} Applied scroll step, 0 when no scrolling occurred.
 */
function scrollListOutsidePointer(pointerY) {
  const list = document.getElementById("order-editor-list");
  const rect = list.getBoundingClientRect();

  let distance = 0;
  let direction = 0;

  if (pointerY < rect.top) {
    distance = rect.top - pointerY;
    direction = -1;
  } else if (pointerY > rect.bottom) {
    distance = pointerY - rect.bottom;
    direction = 1;
  } else {
    return 0;
  }

  const cap = Math.max(40, list.scrollHeight / 40);
  const speed = Math.min(cap, 2 + distance / 4 + (distance * distance) / 700);
  const step = Math.round(speed) * direction;

  const before = list.scrollTop;

  list.scrollTop = before + step;

  return list.scrollTop === before ? 0 : step;
}

/**
 * Color codes a row in place: the danger color for a row the user
 * actually dragged, and the softer "changed" tint for a row that only
 * shifted because a neighbour moved past it. Marking both the same way
 * made the two cases impossible to tell apart.
 *
 * @param {HTMLElement} row Row element.
 * @param {number} position Position in the working order.
 * @param {number} questionIndex Question index.
 * @returns {void}
 */
function applyRowState(row, position, questionIndex) {
  const changed = originalOrder[position] !== questionIndex;
  const dragged = changed && draggedItems.has(questionIndex);

  row.classList.toggle("order-dragged", dragged);
  row.classList.toggle("order-changed", changed && !dragged);
}

/**
 * Re-syncs row numbers and the color coding with the current working
 * order, in place (no rebuild).
 *
 * @returns {void}
 */
function updateRowLabels() {
  const list = document.getElementById("order-editor-list");

  list.querySelectorAll(".order-row").forEach((row, position) => {
    const number = row.querySelector(".order-number");

    if (number) {
      number.textContent = `${position + 1}.`;
    }

    applyRowState(row, position, Number(row.dataset.questionIndex));
  });
}

/**
 * Builds the draggable question order list.
 *
 * Rows support both mouse dragging (native drag events) and touch
 * dragging (started immediately from the row's grip handle). The row of
 * the question the editor is on is marked, since adding next to it or
 * deleting it acts on that one.
 *
 * @returns {void}
 */
function buildOrderList() {
  const list = document.getElementById("order-editor-list");

  list.replaceChildren();

  workingOrder.forEach((questionIndex, position) => {
    const row = document.createElement("div");
    row.className = "order-row";
    row.draggable = true;

    // Color code rows moved away from the order the editor opened with
    applyRowState(row, position, questionIndex);

    if (questionIndex === state.currentQuestionIndex) {
      row.classList.add("order-current");
      row.setAttribute("aria-current", "true");
    }

    const number = document.createElement("span");
    number.className = "order-number";
    number.textContent = `${position + 1}.`;

    const caption = document.createElement("span");
    caption.className = "order-caption";
    caption.textContent = getQuestionSnippet(questionIndex);

    row.dataset.questionIndex = String(questionIndex);

    /*
     * Touch reordering moves rows in place (no rebuild), so a position
     * captured once here can go stale: resolve it from the row's
     * question index whenever a handler runs.
     */
    const currentPosition = () =>
      workingOrder.indexOf(Number(row.dataset.questionIndex));

    /*
     * Grip handle: the only place a touch drag starts. It owns its own
     * gesture (touch-action: none), so the drag arms immediately and
     * cannot be stolen by a scroll; the row body keeps native touch
     * scrolling and pinch zoom.
     */
    const handle = document.createElement("span");
    handle.className = "order-handle";
    handle.textContent = "⠿";

    handle.addEventListener("pointerdown", (event) => {
      if (event.pointerType === "mouse") {
        return;
      }

      /*
       * Only the primary pointer starts a drag. isPrimary is a
       * property of the event, not tracked state, so a missed pointer
       * event can never leave this permanently false (a counter or a
       * set of active pointers can, which used to lock dragging out
       * until the editor was reopened).
       */
      if (!event.isPrimary) {
        return;
      }

      startGripDrag(event, currentPosition());
    });

    /*
     * Block the native long-press behaviors (text lift, selection
     * callout) on the handle. Safe here, unlike on the row body: the
     * handle does not scroll, so canceling touchstart costs nothing.
     */
    handle.addEventListener(
      "touchstart",
      (event) => {
        if (event.touches.length === 1) {
          event.preventDefault();
        }
      },
      { passive: false },
    );

    row.appendChild(handle);
    row.appendChild(number);
    row.appendChild(caption);

    row.addEventListener("dragstart", (event) => {
      /*
       * Android/iOS turn a long press on a draggable element into a
       * native HTML5 drag - a ghost that preempts everything else.
       * Only mouse drags may use the native mechanism.
       */
      if (lastPointerType !== "mouse") {
        event.preventDefault();

        return;
      }

      startMouseDrag(event, currentPosition(), row);
    });

    /*
     * Picking a row makes it the question the buttons in the list act
     * on, and the one the editor shows. A drag does not produce a click
     * (the gesture is claimed by the drag), so this is a tap only.
     */
    row.addEventListener("click", () => selectQuestion(questionIndex));

    list.appendChild(row);
  });
}

document
  .getElementById("order-editor-save")
  .addEventListener("click", saveOrder);
document
  .getElementById("order-editor-cancel")
  .addEventListener("click", cancelOrderEditor);
document
  .getElementById("order-editor-add")
  .addEventListener("click", () => addOrderQuestion("end"));
document
  .getElementById("order-editor-add-before")
  .addEventListener("click", () => addOrderQuestion("before"));
document
  .getElementById("order-editor-add-after")
  .addEventListener("click", () => addOrderQuestion("after"));
document
  .getElementById("order-editor-delete")
  .addEventListener("click", deleteCurrentQuestion);
