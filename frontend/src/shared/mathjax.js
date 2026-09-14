import { state } from "../state.js";

export function loadMathJax(enabled) {

    if (!enabled) {
        state.mathReady = false;
        Promise.resolve(false);
        return;
    }

    window.MathJax = {
        tex: {
            inlineMath: [
                ["$", "$"],
                ["\\(", "\\)"],
            ],
        },
    };

    return new Promise((resolve) => {

        const script = document.createElement("script");
        script.src =
            "https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js";

        script.onload = () => {
            state.mathReady = true;
            resolve(true);
        };

        script.onerror = () => {
            state.mathReady = false;
            resolve(false);
        };

        document.head.appendChild(script);
    });
}
