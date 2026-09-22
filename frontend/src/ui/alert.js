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

  yesButton.onclick = () => {
    prompt.classList.remove("visible");
    if (onYes) onYes();
  };

  noButton.onclick = () => {
    prompt.classList.remove("visible");
    if (onNo) onNo();
  };

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

  yesButton.onclick = () => {
    prompt.classList.remove("visible");
  };

  prompt.classList.add("visible");
}
