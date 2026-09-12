import { formatTime } from "./shared/formatting.js"
import { state } from "./state.js";


const timerElement = document.getElementById("timer");

function getTimerKey(quizStorageKey) {
    return `quizTimer_${quizStorageKey}`;
}

function loadTimer(state) {
    try {
        const data = JSON.parse(localStorage.getItem(getTimerKey(state.quizStorageKey)));

        state.timer.elapsed = data?.elapsed || 0;
        state.timer.start = data?.start || null;
    } catch {
        state.timer.elapsed = 0;
        state.timer.start = null;
    }
}

export function saveTimer() {
    try {
        localStorage.setItem(
            getTimerKey(state.quizStorageKey),
            JSON.stringify({
                elapsed: state.timer.elapsed,
                start: state.timer.start,
            }),
        );
    } catch { }
}

export function updateTimer() {
    if (!state.timer.start) return;

    const elapsed = state.timer.elapsed + Math.floor((Date.now() - state.timer.start) / 1000);

    timerElement.textContent = formatTime(elapsed);
}

export function toggleTimer() {

    state.timer.visible = !state.timer.visible;

    timerElement.classList.toggle("visible", state.timer.visible);

    if (state.timer.visible) {
        loadTimer(state);

        // Start
        if (!state.timer.start) {
            state.timer.start = Date.now();
            saveTimer();
        }

        updateTimer();
        state.timer.interval = setInterval(updateTimer, 1000);
    } else {
        // Pause
        if (state.timer.start) {
            state.timer.elapsed += Math.floor((Date.now() - state.timer.start) / 1000);

            state.timer.start = null;
            saveTimer();
        }

        clearInterval(state.timer.interval);
        state.timer.interval = null;
    }
}
