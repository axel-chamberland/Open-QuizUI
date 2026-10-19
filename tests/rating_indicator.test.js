/**
 * @vitest-environment jsdom
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  hideRatingIndicator,
  showRatingIndicator,
} from "../frontend/src/ui/rating_indicator.js";

const indicator = () => document.getElementById("rating-indicator");

describe("rating indicator", () => {
  beforeEach(() => {
    vi.useFakeTimers();

    document.body.innerHTML = '<div id="rating-indicator"></div>';
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows the icon of the rating given", () => {
    showRatingIndicator("Again");

    expect(indicator().textContent).toBe("✗");
    expect(indicator().classList.contains("again")).toBe(true);
    expect(indicator().classList.contains("visible")).toBe(true);

    showRatingIndicator("Easy");

    expect(indicator().textContent).toBe("✓✓");
    expect(indicator().classList.contains("easy")).toBe(true);
  });

  it("gives every rating its own icon and colour", () => {
    const expected = {
      Again: "✗",
      Hard: "✓",
      Good: "✓",
      Easy: "✓✓",
    };

    for (const [rating, icon] of Object.entries(expected)) {
      showRatingIndicator(rating);

      expect(indicator().textContent).toBe(icon);
      expect(indicator().classList.contains(rating.toLowerCase())).toBe(true);
    }
  });

  it("drops the colour of the previous rating", () => {
    showRatingIndicator("Again");
    showRatingIndicator("Hard");

    expect(indicator().classList.contains("again")).toBe(false);
    expect(indicator().classList.contains("hard")).toBe(true);
  });

  it("fades out on its own", () => {
    showRatingIndicator("Good");

    vi.advanceTimersByTime(1999);
    expect(indicator().classList.contains("visible")).toBe(true);

    vi.advanceTimersByTime(1);
    expect(indicator().classList.contains("visible")).toBe(false);
  });

  it("keeps a rating given while the previous one is up", () => {
    showRatingIndicator("Again");

    vi.advanceTimersByTime(1500);
    showRatingIndicator("Easy");

    vi.advanceTimersByTime(1500);

    expect(indicator().textContent).toBe("✓✓");
    expect(indicator().classList.contains("visible")).toBe(true);
  });

  it("hides on demand, dropping a scheduled fade out", () => {
    showRatingIndicator("Hard");

    hideRatingIndicator();

    expect(indicator().classList.contains("visible")).toBe(false);

    vi.advanceTimersByTime(2000);

    expect(indicator().textContent).toBe("✓");
  });

  it("ignores an unknown rating", () => {
    showRatingIndicator("Nope");

    expect(indicator().textContent).toBe("");
    expect(indicator().classList.contains("visible")).toBe(false);
  });

  it("does nothing without the indicator in the page", () => {
    document.body.innerHTML = "";

    expect(() => showRatingIndicator("Good")).not.toThrow();
    expect(() => hideRatingIndicator()).not.toThrow();
  });
});
