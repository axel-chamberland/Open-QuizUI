import { state } from "../state.js";

// Download as HTML.
export function downloadQuizHTML(filename = state.quiz.title) {
    // quiz is the current runtime-modified quiz
    const appData = {
        enableMathJax: state.mathReady,
        quiz: state.quiz,
    };

    // Clone the document so the live page is not modified.
    const documentClone = document.documentElement.cloneNode(true);

    // Replace the JSON payload in the cloned document.
    const dataScript = documentClone.querySelector("#app-data");

    if (!dataScript) {
        throw new Error("Could not find #app-data");
    }

    dataScript.textContent = JSON.stringify(appData, null, 2);

    // Serialize the cloned document.
    const html = "<!DOCTYPE html>\n" + documentClone.outerHTML;

    const blob = new Blob([html], { type: "text/html" });
    const url = URL.createObjectURL(blob);

    const a = document.createElement("a");
    a.href = url;
    a.download = filename.endsWith(".html") ? filename : filename + ".html";

    document.body.appendChild(a);
    a.click();
    a.remove();

    URL.revokeObjectURL(url);
}
