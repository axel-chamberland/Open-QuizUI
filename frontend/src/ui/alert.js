export function showPrompt(
  message,
  onYes = null,
  onNo = null,
  yesText = "yes",
  noText = "no",
) {
  const prompt = document.getElementById("global-prompt");
  const messageElement = document.getElementById("global-prompt-message");
  const yesButton = document.getElementById("global-prompt-yes");
  const noButton = document.getElementById("global-prompt-no");

  messageElement.textContent = message;
  yesButton.textContent = yesText;
  noButton.textContent = noText;

  yesButton.style.display = "";
  noButton.style.display = "";

  const close = (callback) => {
    prompt.classList.remove("visible");
    document.removeEventListener("keydown", keyHandler, true);
    if (callback) callback();
  };

  yesButton.onclick = () => close(onYes);
  noButton.onclick = () => close(onNo);

  function keyHandler(e) {
    if (e.key === "Enter" || e.key.toLowerCase() === "y") {
      e.preventDefault();
      e.stopPropagation();
      close(onYes);
    } else if (e.key.toLowerCase() === "n" || e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      close(onNo);
    }
  }

  document.addEventListener("keydown", keyHandler, true);
  prompt.classList.add("visible");
}

export function showAlert(message) {
  const prompt = document.getElementById("global-prompt");
  const messageElement = document.getElementById("global-prompt-message");
  const yesButton = document.getElementById("global-prompt-yes");
  const noButton = document.getElementById("global-prompt-no");

  messageElement.textContent = message;
  yesButton.textContent = "OK";

  yesButton.style.display = "";
  noButton.style.display = "none";

  const close = () => {
    prompt.classList.remove("visible");
    document.removeEventListener("keydown", keyHandler, true);
  };

  yesButton.onclick = close;

  function keyHandler(e) {
    if (e.key === "Enter" || e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      close();
    }
  }

  document.addEventListener("keydown", keyHandler, true);
  prompt.classList.add("visible");
}
