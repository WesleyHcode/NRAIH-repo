document.addEventListener("DOMContentLoaded", () => {
    const savedHTML = localStorage.getItem("savedMediaReport");
    const savedTopic = localStorage.getItem("savedMediaTopic");

    if (savedHTML) {
        document.getElementById("promptOutput").innerHTML = savedHTML;
    }
    if (savedTopic) {
        document.getElementById("promptInput").value = savedTopic;
    }
}
);

const delay = ms => new Promise(res => setTimeout(res, ms));

async function sendPrompt(retryCount = 0) {
    const inputText = document.getElementById("promptInput").value;
    const outputText = document.getElementById("promptOutput");
    const maxRetries = 3;

    if (!inputText.trim()) {
        outputText.innerText = "Please enter a news topic first"
        return;
    }

    if (retryCount === 0) {
        outputText.innerText = "Loading...";
    } else {
        outputText.innerHTML = `<em>Rate limit hit. Retrying analysis (Attempt ${retryCount}/${maxRetries}). Please wait...</em>`;
    }

    try {
        const response = await fetch("http://127.0.0.1:8000/api/analyze-topic", 
            {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({topic: inputText})
            }
        );

        const data = await response.json();
        
        if (!response.ok) {
            outputText.innerText =
                data.detail || "Analysis failed. Please try again.";
            return;
        }

        if (!Array.isArray(data.analyses)) {
            outputText.innerText = "Invalid response from the server.";
            return;
        }

        if (data.analyses.length === 0) {
            outputText.innerText = "No articles found for this topic.";
            return;
        }

        const htmlCardLayout = document.createElement("div");
        htmlCardLayout.style.cssText =
            "display:flex;flex-direction:column;gap:20px;";

        data.analyses.forEach((article, index) => {
            const card = document.createElement("div");
            card.style.cssText = 
                "background:#ffffff;border:1px solid #e2e8f0;" +
                "border-radius:8px;padding:20px;" +
                "box-shadow:0 1px 3px rgba(0,0,0,0.05);";
            
            const heading = document.createElement("div");
            heading.style.cssText =
                "display:flex;justify-content:space-between;" +
                "align-items:flex-start;gap:12px;margin-bottom:10px;";
            
            const source = document.createElement("span");
            source.style.cssText =
                "font-weight:700;color:#000000;font-size:14px;" +
                "text-transform:uppercase;letter-spacing:0.05em;";
            source.textContent =
                `Source ${index + 1}: ${article.source || "Unknown Source"}`;

            const bias = document.createElement("span");
            bias.textContent = article.bias || "Unknown Bias";
            bias.style.cssText =
                "color:white;padding:4px 10px;font-size:12px;" +
                "font-weight:600;border-radius:20px;background:#64748b;";

            if (article.bias === "Left" || article.bias === "Lean Left") {
                bias.style.background = "#3b82f6";
            } else if (
                article.bias === "Right" || article.bias === "Lean Right"
            ) {
                bias.style.background = "#ef4444";
            }
            heading.append(source, bias);

            const title = document.createElement("h4");
            title.style.cssText =
                "margin:0 0 12px;font-size:16px;color:#000000;";
            title.textContent = article.title || "Untitled Article";

            const perspective = document.createElement("p");
            perspective.style.cssText = "margin:0 0 8px;font-size:14px;";
            perspective.textContent =
                "Framing & Perspective: " +
                (article.perspective || "Not available.");

            const context = document.createElement("p");
            context.style.cssText = "margin:0;font-size:14px;";
            context.textContent =
                "Omitted Context: " + (article.context || "Not available.");

            card.append(heading, title, perspective, context);

            if (article.url) {
                try {
                    const url = new URL(article.url)

                    if (url.protocol === "https:" || url.protocol === "http:") {
                        const link = document.createElement("a");
                        link.href = url.href;
                        link.target = "_blank";
                        link.rel = "noopener noreferrer";
                        link.textContent = "Read Original Article →";
                        link.style.cssText =
                            "display:inline-block;margin-top:15px;" +
                            "color:#2563eb;font-weight:600;" +
                            "text-decoration:none;font-size:14px;";
                        card.appendChild(link);
                    }
                } catch {
                    console.warn("Invalid URL");
                }
            }

            htmlCardLayout.appendChild(card);
        });
        outputText.replaceChildren(htmlCardLayout);
        localStorage.setItem("savedMediaReport", htmlCardLayout.outerHTML);
        localStorage.setItem("savedMediaTopic", inputText.trim());
    } catch(error) {
        outputText.innerText = "Crash: " + error.message;
        console.error(error);
    }
}

function clearDashboard() {
    document.getElementById("promptInput").value = "";
    document.getElementById("promptOutput").innerText = "Your report goes here...";

    localStorage.removeItem("savedMediaReport");
    localStorage.removeItem("savedMediaTopic");
}

document.getElementById("promptInput").addEventListener('keydown', function(event) {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendPrompt();
    }
});
