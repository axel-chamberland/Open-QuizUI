/**
 * Icon of each rating, and the class naming the colour of its button.
 *
 * A card rated ✗ or ✓ in plain flashcard mode is rated "Again" or
 * "Good", so it is shown with the same icons.
 */
const RATINGS = {
  Again: { icon: "✗", className: "again" },
  Hard: { icon: "✓", className: "hard" },
  Good: { icon: "✓", className: "good" },
  Easy: { icon: "✓✓", className: "easy" },
};

/**
 * How long the indicator stays up, in milliseconds.
 */
const VISIBLE_MS = 2000;

let hideTimer = null;

/**
 * Shows the rating of a card in the corner of the page, then fades it
 * out again.
 *
 * A rating given while the previous one is still up replaces it and
 * restarts the fade out.
 *
 * @param {"Again"|"Hard"|"Good"|"Easy"} rating
 * @returns {void}
 */
export function showRatingIndicator(rating) {
  const indicator = document.getElementById("rating-indicator");
  const entry = RATINGS[rating];

  if (!indicator || !entry) {
    return;
  }

  for (const { className } of Object.values(RATINGS)) {
    indicator.classList.remove(className);
  }

  indicator.textContent = entry.icon;
  indicator.classList.add(entry.className, "visible");

  clearTimeout(hideTimer);
  hideTimer = setTimeout(hideRatingIndicator, VISIBLE_MS);
}

/**
 * Hides the indicator at once, dropping a scheduled fade out.
 *
 * @returns {void}
 */
export function hideRatingIndicator() {
  clearTimeout(hideTimer);
  hideTimer = null;

  document.getElementById("rating-indicator")?.classList.remove("visible");
}
