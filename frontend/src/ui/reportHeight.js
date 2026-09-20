function reportHeight() {
  // Do not run when in fullscreen
  if (
    document.fullscreenElement ||
    document.documentElement.classList.contains("pseudo-fullscreen-active")
  )
    return;

  const pages = document.querySelectorAll(".page");

  const visible = [...pages].find((page) => page.style.display !== "none");

  const h = visible.scrollHeight;

  parent.postMessage({ type: "iframe:height", height: h }, "*");
}

export function initHeightReporting() {
  window.addEventListener("load", () => {
    reportHeight();
    new ResizeObserver(reportHeight).observe(document.body);
  });
}
