/**
 * @vitest-environment node
 *
 * Drives the actual quiz page - the single-file HTML the way Open WebUI
 * gets it - in a real headless Chromium, and fails on any uncaught page
 * error or console error, which the jsdom unit tests cannot see.
 *
 * Assumes Playwright's Chromium is on disk: the npm postinstall hook
 * installs it whenever dependencies go in, and CI's workflow step
 * additionally provides the system libraries around it.
 */
import { execFileSync } from "node:child_process";
import { writeFileSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterAll, afterEach, describe, expect, it } from "vitest";
import { chromium } from "playwright";

const root = dirname(dirname(fileURLToPath(import.meta.url)));

/*
 * The page under test is the HTML the way Open WebUI gets it, so the
 * source of truth is a full build of the current source, executed by
 * wrap_html() itself - not frontend/index.html, and not the template
 * spliced out of the release file by hand. The renderer below writes
 * the generated action function and answers it for the app data (JSON
 * payload on stdin, document on stdout).
 *
 * (Not a test-path regex or local replace(): the template carries
 * adjacent quote characters, which the module transform rewrites, so
 * anything parsed out of the release file by JavaScript is unreliable
 * - and would stop wrap_html() being what is under test anyway.)
 */
const pythonExecutable = () => {
  /*
   * Local dev keeps an interpreter in .venv (bare pytest is not on
   * PATH there either); CI installs into the interpreter, so fall
   * back to whatever `python` resolves to.
   */
  for (const candidate of [
    process.env.PYTHON_BIN,
    join(root, ".venv", "bin", "python"),
    "python",
    "python3",
  ]) {
    if (candidate === undefined) {
      continue;
    }

    try {
      execFileSync(candidate, ["-c", "pass"], { stdio: "ignore" });

      return candidate;
    } catch {
      // Not useable; try the next one.
    }
  }

  throw new Error("No Python interpreter found to render the test page");
};

const python = pythonExecutable();

const generateHTML = (payload) => {
  const document = execFileSync(python, ["tests/browser_page.py"], {
    // stdout can exceed Node's small default buffer.
    cwd: root,
    encoding: "utf8",
    input: JSON.stringify(payload),
    maxBuffer: 50 * 1024 * 1024,
  });

  if (!document.trimEnd().endsWith("</html>")) {
    throw new Error("The renderer did not produce the full document");
  }

  return document;
};

const appData = {
  enableMathJax: false,
  mode: "mcq",
  srsQueueSize: 20,
  requestRetention: 0.9,
  srsOnLoad: false,
  quiz: {
    title: "Browser smoke quiz",
    questions: [
      {
        question: "First question?",
        options: ["wrong", "right", "wrong"],
        correct_index: 1,
        explanation: "one",
      },
      {
        question: "Second question?",
        options: ["right", "wrong", "wrong"],
        correct_index: 0,
        explanation: "two",
      },
    ],
  },
};

const html = generateHTML(appData);

/*
 * The page renders a question with a single option as a flashcard, which
 * is what the action function produces for a flashcard message.
 */
const flashcardData = {
  enableMathJax: false,
  mode: "flashcard",
  srsQueueSize: 20,
  requestRetention: 0.9,
  srsOnLoad: false,
  quiz: {
    title: "Browser smoke flashcards",
    questions: [
      {
        question: "First card?",
        options: ["first answer"],
        correct_index: 0,
        explanation: "one",
      },
      {
        question: "Second card?",
        options: ["second answer"],
        correct_index: 0,
      },
    ],
  },
};

const flashcardHtml = generateHTML(flashcardData);

/*
 * The question list only scrolls once it overflows the 60vh it tops out
 * at, so the auto-scroll checks below need a quiz longer than the list.
 */
const longQuizData = {
  enableMathJax: false,
  mode: "mcq",
  srsQueueSize: 20,
  requestRetention: 0.9,
  srsOnLoad: false,
  quiz: {
    title: "Browser smoke long quiz",
    questions: Array.from({ length: 40 }, (_, index) => ({
      question: `Question ${index + 1}?`,
      options: ["right", "wrong"],
      correct_index: 0,
      explanation: `${index + 1}`,
    })),
  },
};

const longHtml = generateHTML(longQuizData);

/*
 * The results page lists a correction for every question, so once it is
 * embedded it has to scroll in a capped column instead of reporting its
 * whole height to the hosting page. These corrections overflow that cap.
 */
const correctionsData = {
  enableMathJax: false,
  mode: "mcq",
  srsQueueSize: 20,
  requestRetention: 0.9,
  srsOnLoad: false,
  quiz: {
    title: "Browser smoke corrections",
    questions: Array.from({ length: 8 }, (_, index) => ({
      question: `Correction ${index + 1}?`,
      options: ["wrong", "right"],
      correct_index: 1,
      explanation:
        "A correction long enough that the results column has to scroll. ".repeat(
          6,
        ),
    })),
  },
};

const correctionsHtml = generateHTML(correctionsData);

const browser = await chromium.launch();
const errors = [];

const page = await browser.newPage();

// Any uncaught exception in the page.
page.on("pageerror", (error) => errors.push(`pageerror: ${error.stack}`));

// Most app bugs come back as console errors instead of exceptions.
page.on("console", (message) => {
  if (message.type() !== "error") {
    return;
  }

  const location = message.location();

  if (
    location.url.includes(
      "raw.githubusercontent.com/axel-chamberland/Open-QuizUI/main/frontend/assets/action_logo.svg",
    )
  ) {
    // The favicon is an external asset, not app code; a failed load
    // must not shadow real app errors (and the test may be offline).
    return;
  }

  errors.push(`console.error: ${message.text()} (${location.url})`);
});

afterAll(async () => {
  await browser.close();
});

afterEach(() => {
  if (errors.length > 0) {
    throw new Error(`Page errors:\n${errors.join("\n")}`);
  }
});

/**
 * Confirms an element is visible.
 *
 * @param {string} selector CSS selector.
 * @param {string} label What it is for the failure message.
 * @returns {Promise<void>}
 */
async function visible(selector, label) {
  await page
    .locator(selector)
    .first()
    .waitFor({ state: "visible", timeout: 10_000 })
    .catch(() => {
      throw new Error(`Not visible: ${label} (${selector})`);
    });
}

/**
 * Opens the question list on a page, through the app's own menu.
 *
 * @param {string} file Path of the rendered page to load.
 * @returns {Promise<void>}
 */
async function openQuestionList(file) {
  await page.goto(`file://${file}`);
  await visible("#question", "question box");

  await page.click("#mcq-menu-button");
  await page.click("#mcq-dropdown-menu .editor-button");
  await visible("#editor", "editor page");

  /* "Edit Questions" lives inside the collapsible settings fold. */
  await page.click("#editor-additional-settings summary");
  await page.click("#order-editor-open-button");
  await visible("#order-editor-list", "question list");
}

describe("browser smoke", () => {
  it("answers, revisits, and manages questions without page errors", async () => {
    const directory = mkdtempSync(join(tmpdir(), "openquizui-smoke-"));

    writeFileSync(join(directory, "quiz.html"), html);

    await page.goto(`file://${join(directory, "quiz.html")}`);
    await visible("#question", "question box");

    /* Answering correctly reveals the explanation. */
    await page.click('#options button.option:has-text("right")');
    await visible("#explanation", "explanation");

    /* Next moves to the second question. */
    await page.click("#question-box .next-button");
    await page.waitForFunction(() =>
      document.getElementById("question").textContent.includes("Second"),
    );

    await page.click('#options button.option:has-text("right")');
    await visible("#explanation", "explanation of the second question");

    /* Next past the last question is the results page. */
    await page.click("#question-box .next-button");
    await visible("#results", "results page");

    await page.click("#results-back-button");
    await visible("#question-box", "question box again");

    /* Copying as flashcards runs and closes the menu again. */
    await page.click("#mcq-menu-button");
    await page.click("#mcq-dropdown-menu .copy-flashcards-button");
    await page
      .locator("#mcq-dropdown-menu")
      .waitFor({ state: "hidden", timeout: 5_000 });

    /* The editor opens through the page's own dropdown menu. */
    await page.click("#mcq-menu-button");
    await page.click("#mcq-dropdown-menu .editor-button");
    await visible("#editor", "editor page");
    expect(await page.textContent("#editor-question-number")).toContain("2");

    /* The question list lists both questions as rows. */
    /* "Edit Questions" lives inside the collapsible settings fold. */
    await page.click("#editor-additional-settings summary");
    await page.click("#order-editor-open-button");
    await visible("#order-editor-list", "question list");

    const rows = page.locator("#order-editor-list .order-row");

    expect(await rows.count()).toBe(2);

    /* Picking a row moves the editor to that question; the list stays open. */
    await page.click('.order-row[data-question-index="1"]');
    await page.waitForFunction(
      () =>
        document
          .querySelector("#editor-question textarea")
          .value.includes("Second"),
      { timeout: 5_000 },
    );

    /* Add a question before and one after the current row. */
    await page.click("#order-editor-add-before");
    await page.waitForFunction(
      () =>
        document.querySelectorAll("#order-editor-list .order-row").length === 3,
      { timeout: 5_000 },
    );

    await page.click("#order-editor-add-after");
    await page.waitForFunction(
      () =>
        document.querySelectorAll("#order-editor-list .order-row").length === 4,
      { timeout: 5_000 },
    );

    /* Deleting is confirmed with a prompt. */
    await page.click("#order-editor-delete");
    await page.click("#global-prompt-yes");
    await page.waitForFunction(
      () =>
        document.querySelectorAll("#order-editor-list .order-row").length === 3,
      { timeout: 5_000 },
    );

    /* Save the staged order; the list closes with the editor open. */
    await page.click("#order-editor-save");
    await page
      .locator("#order-editor")
      .waitFor({ state: "hidden", timeout: 5_000 });

    /*
     * Save an edit so the alert for a saved change comes up, then
     * close the editor - which also closes the question list.
     */
    await page.fill("#editor-question textarea", "Saved through a click.");

    await page.click("#editor-save-button");
    await visible(".global-prompt", "saved alert");
    expect(await page.textContent("#global-prompt-message")).toBe(
      "Changes saved.",
    );
    await page.click("#global-prompt-yes");

    /* Closing the editor asks first, and also closes the list. */
    await page.click("#editor-close-button");
    await page.click("#global-prompt-yes");
    await page.locator("#editor").waitFor({ state: "hidden", timeout: 5_000 });
    await page
      .locator("#order-editor")
      .waitFor({ state: "hidden", timeout: 5_000 });

    expect(errors).toEqual([]);
  }, 60_000);

  it("reveals and rates flashcards without page errors", async () => {
    const directory = mkdtempSync(join(tmpdir(), "openquizui-flashcards-"));

    writeFileSync(join(directory, "flashcards.html"), flashcardHtml);

    await page.goto(`file://${join(directory, "flashcards.html")}`);
    await visible("#flashcard-box", "flashcard box");

    expect(await page.textContent(".flashcard-question")).toContain(
      "First card?",
    );

    /* The answer stays hidden until the card is revealed. */
    expect(await page.locator(".flashcard-answer").isVisible()).toBe(false);

    await page.keyboard.press("Enter");
    await visible(".flashcard-answer", "revealed answer");
    await visible(".flashcard-explanation", "revealed explanation");
    expect(await page.textContent(".flashcard-answer")).toContain(
      "first answer",
    );

    /* Pressing 1 rates the card unknown and moves to the next one,
         with its answer still hidden, showing the rating in the corner
         of the page for a moment. */
    await page.keyboard.press("1");
    expect(await page.textContent("#rating-indicator")).toBe("✗");
    await page.waitForFunction(
      () =>
        document
          .querySelector(".flashcard-question")
          .textContent.includes("Second"),
      { timeout: 5_000 },
    );
    expect(await page.locator(".flashcard-answer").isVisible()).toBe(false);

    /* The rating fades out on its own. */
    await page
      .locator("#rating-indicator")
      .waitFor({ state: "hidden", timeout: 5_000 });

    /* Rating the last card leads to the results page, where both
         ratings are counted: one unknown, one known. */
    await page.keyboard.press("Enter");
    await visible(".flashcard-answer", "revealed answer of the last card");
    await page.click("#flashcard-rating .known-button");
    await visible("#results", "results page");

    expect(await page.textContent("#score")).toBe("Score: 1/2");
    expect(await page.textContent("#question-corrections article")).toContain(
      "✗",
    );

    expect(errors).toEqual([]);
  }, 60_000);

  /*
   * A drag only keeps scrolling when something drives it while the
   * pointer is held still: neither a mouse drag nor a finger sends
   * events then, and the browser's own auto-scroll waits for the next
   * mouse move (which is why the list used to stall until it was
   * jerked). Both drags below are left alone after one move, so only
   * the list's own auto-scroll can be moving them.
   *
   * They are driven with the events a real drag produces rather than
   * with Playwright's mouse, which reaches a headless browser as plain
   * mouse input and never starts a native drag.
   */
  it("keeps the list scrolling while a mouse drag is held past it", async () => {
    const directory = mkdtempSync(join(tmpdir(), "openquizui-order-mouse-"));

    writeFileSync(join(directory, "long.html"), longHtml);

    await openQuestionList(join(directory, "long.html"));

    /* Drag the first row, put the pointer 24px below the list, and
         send nothing else, the way a held mouse does. */
    const pointer = await page.evaluate(() => {
      const row = document.querySelector("#order-editor-list .order-row");
      const list = document.getElementById("order-editor-list");
      const rowBox = row.getBoundingClientRect();
      const box = list.getBoundingClientRect();
      const event = (type, x, y) =>
        new DragEvent(type, {
          bubbles: true,
          cancelable: true,
          clientX: x,
          clientY: y,
        });

      row.dispatchEvent(
        event("dragstart", rowBox.x + 20, rowBox.y + rowBox.height / 2),
      );
      list.dispatchEvent(event("dragover", box.x + 20, box.bottom + 24));

      return { x: box.x + 20, y: box.bottom + 24 };
    });

    await page.waitForTimeout(600);

    expect(
      await page.evaluate(
        () => document.getElementById("order-editor-list").scrollTop,
      ),
    ).toBeGreaterThan(100);

    /* The slot the pointer is over stays marked while the list scrolls
         under it, which the browser cannot do without mouse movement. */
    expect(
      await page.locator("#order-editor-list .order-drop-target").count(),
    ).toBe(1);

    /* Releasing there drops the row where the pointer is, not where
         the row under it was when it was last reported. */
    await page.evaluate((drop) => {
      document.getElementById("order-editor-list").dispatchEvent(
        new DragEvent("drop", {
          bubbles: true,
          cancelable: true,
          clientX: drop.x,
          clientY: drop.y,
        }),
      );
    }, pointer);

    const order = await page.evaluate(() =>
      [...document.querySelectorAll("#order-editor-list .order-row")].map(
        (row) => row.dataset.questionIndex,
      ),
    );

    expect(order).toHaveLength(40);
    expect(order[0]).not.toBe("0");
    expect(order.indexOf("0")).toBeGreaterThan(0);
    expect(order.filter((index) => index === "0")).toHaveLength(1);
    expect(
      await page.locator("#order-editor-list .order-dragging").count(),
    ).toBe(0);
  }, 60_000);

  it("keeps the list scrolling while a touch drag is held past it", async () => {
    const directory = mkdtempSync(join(tmpdir(), "openquizui-order-touch-"));

    writeFileSync(join(directory, "long.html"), longHtml);

    await openQuestionList(join(directory, "long.html"));

    /* The grip starts the drag; a single move past the list follows,
         and then nothing, the way a held finger sends nothing. */
    await page.evaluate(() => {
      const handle = document.querySelector("#order-editor-list .order-handle");
      const list = document.getElementById("order-editor-list");
      const handleBox = handle.getBoundingClientRect();
      const box = list.getBoundingClientRect();
      const event = (type, x, y) =>
        new PointerEvent(type, {
          bubbles: true,
          cancelable: true,
          pointerId: 1,
          pointerType: "touch",
          isPrimary: true,
          clientX: x,
          clientY: y,
        });

      handle.dispatchEvent(
        event(
          "pointerdown",
          handleBox.x + 5,
          handleBox.y + handleBox.height / 2,
        ),
      );
      document.dispatchEvent(event("pointermove", box.x + 20, box.bottom + 24));
    });

    await page.waitForTimeout(600);

    expect(
      await page.evaluate(
        () => document.getElementById("order-editor-list").scrollTop,
      ),
    ).toBeGreaterThan(100);

    /* The dragged row follows the pointer down the list as it
         scrolls. */
    const order = await page.evaluate(() =>
      [...document.querySelectorAll("#order-editor-list .order-row")].map(
        (row) => row.dataset.questionIndex,
      ),
    );

    expect(order).toHaveLength(40);
    expect(order[0]).not.toBe("0");
    expect(order.indexOf("0")).toBeGreaterThan(0);

    /* Lifting the finger ends the drag where it stands. */
    await page.evaluate(() => {
      document.dispatchEvent(
        new PointerEvent("pointerup", {
          bubbles: true,
          cancelable: true,
          pointerId: 1,
          pointerType: "touch",
          isPrimary: true,
          clientX: 400,
          clientY: 800,
        }),
      );
    });

    expect(
      await page.locator("#order-editor-list .order-dragging").count(),
    ).toBe(0);
    expect(
      await page.evaluate(() =>
        [...document.querySelectorAll("#order-editor-list .order-row")].map(
          (row) => row.dataset.questionIndex,
        ),
      ),
    ).toEqual(order);
  }, 60_000);

  it("scrolls the results inside the hosting iframe instead of growing it", async () => {
    const directory = mkdtempSync(join(tmpdir(), "openquizui-embedded-"));

    writeFileSync(join(directory, "quiz.html"), correctionsHtml);

    /*
     * A host page shaped like Open WebUI's message content: an iframe
     * sized from the height the page reports.
     */
    writeFileSync(
      join(directory, "host.html"),
      `<!doctype html>
<html><body style="margin: 0">
<iframe id="quiz" src="quiz.html" style="width: 100%; height: 300px; border: 0"></iframe>
<script>
  window.heights = [];
  window.addEventListener("message", (event) => {
    if (event.data?.type === "iframe:height") {
      window.heights.push(event.data.height);
      document.getElementById("quiz").style.height = event.data.height + "px";
    }
  });
</script>
</body></html>`,
    );

    await page.goto(`file://${join(directory, "host.html")}`);

    const frame = page.frames().find((f) => f.url().endsWith("quiz.html"));

    await frame.waitForSelector("#question");

    /* Answer every question to reach the results page. */
    for (let index = 0; index < correctionsData.quiz.questions.length; index++) {
      await frame.click('#options button.option:has-text("right")');
      await frame.click("#question-box .next-button");
    }

    await frame.waitForSelector("#results");

    /* Let the page report its results height to the host. */
    await frame.evaluate(
      () =>
        new Promise((resolve) =>
          requestAnimationFrame(() => requestAnimationFrame(resolve)),
        ),
    );

    const column = await frame.evaluate(() => {
      const scroll = document.getElementById("results-scroll");

      scroll.scrollTop = 100;

      return {
        embedded: document.body.classList.contains("embedded"),
        maxHeight: getComputedStyle(scroll).maxHeight,
        clientHeight: scroll.clientHeight,
        scrollHeight: scroll.scrollHeight,
        scrolledBy: scroll.scrollTop,
      };
    });

    expect(column.embedded).toBe(true);
    expect(column.maxHeight).toBe("600px");
    expect(column.scrollHeight).toBeGreaterThan(column.clientHeight);
    expect(column.scrolledBy).toBeGreaterThan(0);

    /*
     * And the hosting page stays around the cap: the corrections are
     * taller than that, and without the cap they would all be reported.
     */
    const hostHeight = await page.evaluate(
      () => document.querySelector("#quiz").getBoundingClientRect().height,
    );

    expect(column.scrollHeight).toBeGreaterThan(2000);
    expect(hostHeight).toBeLessThan(900);

    /* Opened as a file of its own, the page is not capped at all. */
    await page.goto(`file://${join(directory, "quiz.html")}`);
    await visible("#question", "question box");

    const standalone = await page.evaluate(() => ({
      embedded: document.body.classList.contains("embedded"),
      maxHeight: getComputedStyle(
        document.getElementById("results-scroll"),
      ).maxHeight,
    }));

    expect(standalone).toEqual({ embedded: false, maxHeight: "none" });
  }, 60_000);

  it("offers each page's documentation in its own menu", async () => {
    const directory = mkdtempSync(join(tmpdir(), "openquizui-docs-"));

    writeFileSync(join(directory, "quiz.html"), html);

    await page.goto(`file://${join(directory, "quiz.html")}`);
    await visible("#question", "question box");

    /*
     * Every page's ⋮ menu holds a docs link, each to the section that
     * covers it: the question pages to taking a quiz (and to flashcards
     * for the flashcard page), the editor to editing a quiz.
     */
    const docs = await page.evaluate(() =>
      ["mcq", "flashcard", "editor"].map(
        (name) =>
          document.querySelector(`#${name}-dropdown-menu .docs-link`)?.href ??
          null,
      ),
    );

    expect(docs).toEqual([
      "https://github.com/axel-chamberland/Open-QuizUI/blob/main/docs/Usage.md#taking-a-quiz",
      "https://github.com/axel-chamberland/Open-QuizUI/blob/main/docs/Usage.md#flashcards",
      "https://github.com/axel-chamberland/Open-QuizUI/blob/main/docs/Usage.md#editing-a-quiz",
    ]);
  });
});
