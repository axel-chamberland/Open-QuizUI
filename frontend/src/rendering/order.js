import { state } from "../state.js";
import { saveQuestionOrder } from "../persistence/question_order.js";
import { updateQuestionCounts, updateQuestionNumbers } from "../quiz.js";

let workingOrder = null;
let originalOrder = null;
let dragIndex = null;
let keyHandler = null;

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
 * Pointer type of the most recent pointer down, so a native HTML5
 * drag (mouse only) can be told apart from touch.
 */
let lastPointerType = "mouse";

document.addEventListener("pointerdown", (event) => {
  lastPointerType = event.pointerType;
}, true);

/**
 * Returns a single-line plain-text snippet of a question, for the
 * question order list.
 *
 * @param {number} questionIndex Index in quiz.questions.
 * @returns {string} Truncated plain-text question.
 */
function getQuestionSnippet(questionIndex) {
  const question = state.quiz.questions[questionIndex];
  const scratch = document.createElement("div");

  scratch.innerHTML = question.question || "";

  const text = scratch.textContent.trim();

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

  originalOrder = state.questionOrder.slice();
  workingOrder = state.questionOrder.slice();

  dragIndex = null;
  draggedItems.clear();
  document.getElementById("order-editor").classList.remove("dragging");

  buildOrderList();

  keyHandler = (e) => {
    if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      closeOrderEditor();
    }
  };

  document.addEventListener("keydown", keyHandler, true);

  document.getElementById("order-editor").classList.add("visible");
}

/**
 * Closes the order editor overlay.
 *
 * @returns {void}
 */
function closeOrderEditor() {
  // Never leave a half-finished drag behind: it would keep its
  // listeners attached and break the next time the editor is used.
  dragCancel?.();

  document.getElementById("order-editor").classList.remove("visible");
  document.removeEventListener("keydown", keyHandler, true);
  keyHandler = null;
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
  }

  closeOrderEditor();
}

/**
 * Restores the staged order to the quiz's natural sequence.
 *
 * Marks every row as changed when the saved order differs.
 *
 * @returns {void}
 */
function resetOrder() {
  workingOrder = Array.from(
    { length: state.quiz.questions.length },
    (_, index) => index,
  );

  // Back to the natural sequence: nothing has been dragged anywhere.
  draggedItems.clear();

  buildOrderList();
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

  // Last pointer position, and the pending auto-scroll frame.
  let lastY = null;
  let frame = null;

  const stopScroll = () => {
    if (frame !== null) {
      cancelAnimationFrame(frame);
      frame = null;
    }
  };

  /*
   * Auto-scroll runs in animation frames rather than per pointermove,
   * so holding the finger past the list keeps scrolling, and it stops
   * the moment the pointer is back over the list (or the list ends).
   */
  const scrollFrame = () => {
    frame = null;

    if (done || lastY === null) {
      return;
    }

    if (scrollListOutsidePointer(lastY) === 0) {
      return;
    }

    // The scroll moved the rows: re-check which slot is under the pointer.
    handlePointerDragOver(lastY);

    frame = requestAnimationFrame(scrollFrame);
  };

  const cleanup = () => {
    if (done) {
      return;
    }

    done = true;

    stopScroll();

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

    lastY = moveEvent.clientY;

    handlePointerDragOver(lastY);

    if (frame === null) {
      frame = requestAnimationFrame(scrollFrame);
    }
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

  const rows = Array.from(list.querySelectorAll(".order-row"));
  const from = rows.indexOf(dragged);

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

  if (target !== from) {
    const reference = target > from ? rows[target].nextSibling : rows[target];

    list.insertBefore(dragged, reference);

    const [item] = workingOrder.splice(from, 1);
    workingOrder.splice(target, 0, item);

    draggedItems.add(Number(dragged.dataset.questionIndex));

    updateRowLabels();
  }
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
  const speed = Math.min(
    cap,
    2 + distance / 4 + (distance * distance) / 700,
  );
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
 * dragging (started immediately from the row's grip handle).
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
    handle.addEventListener("touchstart", (event) => {
      if (event.touches.length === 1) {
        event.preventDefault();
      }
    }, { passive: false });

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

      dragIndex = currentPosition();
      row.classList.add("order-dragging");
    });

    row.addEventListener("dragend", () => {
      dragIndex = null;
      row.classList.remove("order-dragging");
    });

    row.addEventListener("dragover", (event) => {
      event.preventDefault();
      event.stopPropagation();

      if (dragIndex === null || dragIndex === currentPosition()) {
        return;
      }

      row.classList.add("order-drop-target");
    });

    row.addEventListener("dragleave", () => {
      row.classList.remove("order-drop-target");
    });

    row.addEventListener("drop", (event) => {
      event.preventDefault();
      event.stopPropagation();

      row.classList.remove("order-drop-target");

      const position = currentPosition();

      if (dragIndex === null || dragIndex === position) {
        return;
      }

      const [item] = workingOrder.splice(dragIndex, 1);
      workingOrder.splice(position, 0, item);
      dragIndex = null;

      draggedItems.add(item);

      buildOrderList();
    });

    list.appendChild(row);
  });
}

document.getElementById("order-editor-save").addEventListener("click", saveOrder);
document
  .getElementById("order-editor-cancel")
  .addEventListener("click", closeOrderEditor);
document
  .getElementById("order-editor-reset")
  .addEventListener("click", resetOrder);
