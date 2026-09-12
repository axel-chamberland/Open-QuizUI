let pseudoFullscreenState = null;

export async function toggleFullscreen() {
    if (document.fullscreenElement || document.webkitFullscreenElement) {
        if (document.exitFullscreen) await document.exitFullscreen();
        else document.webkitExitFullscreen?.();
        return;
    }
    if (
        document.documentElement.classList.contains("pseudo-fullscreen-active")
    ) {
        document.documentElement.classList.remove("pseudo-fullscreen-active");
        exitPseudoFullscreen();
        return;
    }
    const root = document.documentElement;
    if (root.requestFullscreen) {
        try {
            await root.requestFullscreen();
            return;
        } catch { }
    } else if (root.webkitRequestFullscreen) {
        root.webkitRequestFullscreen();
        return;
    }

    // support for navigators that don't support fullscreen in iframes, such as iOS webkit (thanks, Apple!)
    document.documentElement.classList.add("pseudo-fullscreen-active");
    enterPseudoFullscreen();
}


function enterPseudoFullscreen() {
    const iframe = window.frameElement;

    // Keep track of fullscreen state in case the iframe is reset while in fullscreen (force a page reload)
    const topBody = window.top.document.body;
    topBody.classList.add("pseudo-fullscreen-active");

    pseudoFullscreenState = {
        scrollX: window.top.scrollX,
        scrollY: window.top.scrollY,
        elements: [],
    };

    let el = iframe;

    while (el && el !== document.body) {
        pseudoFullscreenState.elements.push({
            el,
            style: el.getAttribute("style"),
            siblings: [...el.parentElement.children]
                .filter((x) => x !== el)
                .map((x) => [x, x.style.display]),
        });

        el.style.position = "fixed";
        el.style.inset = "0";
        el.style.width = "100vw";
        el.style.height = "100dvh";
        el.style.margin = "0";
        el.style.maxWidth = "none";
        el.style.maxHeight = "none";
        el.style.zIndex = "999999";

        for (const child of el.parentElement.children) {
            if (child !== el) child.style.display = "none";
        }

        el = el.parentElement;
    }
}

function exitPseudoFullscreen() {
    const topBody = window.top.document.body;

    topBody.classList.remove("pseudo-fullscreen-active");

    if (!pseudoFullscreenState) {
        return;
    }

    const { elements, scrollX, scrollY } = pseudoFullscreenState;

    for (const item of elements) {
        if (item.style === null) item.el.removeAttribute("style");
        else item.el.setAttribute("style", item.style);

        for (const [sibling, display] of item.siblings)
            sibling.style.display = display;
    }

    pseudoFullscreenState = null;

    // Return the top page to where it was.
    window.top.scrollTo(scrollX, scrollY);

    // Make sure the iframe itself is visible.
    window.frameElement.scrollIntoView({
        block: "center",
        inline: "nearest",
    });
}
