/**
 * @vitest-environment node
 *
 * Drives the actual quiz page - the single-file HTML the way Open WebUI
 * gets it - in a real headless Chromium, and fails on any uncaught page
 * error or console error, which the jsdom unit tests cannot see.
 *
 * Needs a Chromium: run `npx playwright install chromium` (CI does it
 * as a workflow step).
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
  const document = execFileSync(
    python,
    ["tests/browser_page.py"],
    {
      // stdout can exceed Node's small default buffer.
      cwd: root,
      encoding: "utf8",
      input: JSON.stringify(payload),
      maxBuffer: 50 * 1024 * 1024,
    },
  );

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

describe("browser smoke", () => {
  it(
    "answers, revisits, and manages questions without page errors",
    async () => {
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
          document.querySelector("#editor-question textarea").value.includes(
            "Second",
          ),
        { timeout: 5_000 },
      );

      /* Add a question before and one after the current row. */
      await page.click("#order-editor-add-before");
      await page.waitForFunction(
        () =>
          document.querySelectorAll("#order-editor-list .order-row").length ===
          3,
        { timeout: 5_000 },
      );

      await page.click("#order-editor-add-after");
      await page.waitForFunction(
        () =>
          document.querySelectorAll("#order-editor-list .order-row").length ===
          4,
        { timeout: 5_000 },
      );

      /* Deleting is confirmed with a prompt. */
      await page.click("#order-editor-delete");
      await page.click("#global-prompt-yes");
      await page.waitForFunction(
        () =>
          document.querySelectorAll("#order-editor-list .order-row").length ===
          3,
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
      await page
        .locator("#editor")
        .waitFor({ state: "hidden", timeout: 5_000 });
      await page
        .locator("#order-editor")
        .waitFor({ state: "hidden", timeout: 5_000 });

      expect(errors).toEqual([]);
    },
    60_000,
  );
});
