function reportHeight() {
    // Do not run when in fullscreen
    if (document.fullscreenElement || document.documentElement.classList.contains("pseudo-fullscreen-active")) return;


    const questionBox = document.querySelector(".question-box");
    const results = document.getElementById("results");
    const editor = document.getElementById("editor");

    const visible =
        questionBox.style.display !== "none"
            ? questionBox
            : results.style.display !== "none"
                ? results
                : editor;

    const h = visible.scrollHeight;

    parent.postMessage({ type: "iframe:height", height: h }, "*");
}

export function initHeightReporting() {
    window.addEventListener("load", () => {
        reportHeight();
        new ResizeObserver(reportHeight).observe(document.body);
    });
}
