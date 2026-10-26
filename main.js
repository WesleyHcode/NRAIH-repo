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
        
        if (data && data.response === "") {
            if (retryCount < maxRetries) {
                const waitTime = (retryCount + 1) * 3000;
                console.warn(`Empty response received. Retrying in ${waitTime/1000}s...`);
                await delay(waitTime);
                return sendPrompt(retryCount + 1);
            } else {
                outputText.innerHTML = "<strong>Groq Free-Tier Rate Limit Overload</strong><br>" +
                                       "The AI servers are currently rate-limiting your workspace. " +
                                       "Please wait 60 seconds for your rate limit bucket to reset, then try searching again.";
                return;
            }
        }
        if (data && data.response) {
            const rawText = data.response;
            console.log("Raw Groq response:", rawText);
            const articleBlocks = rawText.match(
                /<analysis_data>([\s\S]*?)<\/analysis_data>/g
            );

            if (!articleBlocks || articleBlocks.length === 0) {
                console.error("Could not parse Groq response:", rawText);
                outputText.innerHTML = "<strong>Could not parse the AI response.</strong><br>" +
                                        "The AI returned a response, but it did not match the expected article format.";
                return;
            }

            let htmlCardLayout = '<div style="display: flex; flex-direction: column; gap: 20px;">';

            articleBlocks.forEach((block, index) => {
                const cleanBlock = block.replace(/<\/?analysis_data>/g, ' ');

                const sMatch = cleanBlock.match(/SOURCE:\s*(.*)/i);
                const tMatch = cleanBlock.match(/TITLE:\s*(.*)/i);
                const bMatch = cleanBlock.match(/BIAS:\s*(.*)/i);
                const pMatch = cleanBlock.match(/PERSPECTIVE:\s*(.*)/i);
                const cMatch = cleanBlock.match(/CONTEXT:\s*(.*)/i);
                const lMatch = cleanBlock.match(/LINK:\s*(.*)/i);

                const source = (sMatch && sMatch[1]) ? sMatch[1].trim() : "Unknown Source";
                const title = (tMatch && tMatch[1]) ? tMatch[1].trim() : "Unknown Title";
                const bias = (bMatch && bMatch[1]) ? bMatch[1].trim() : "Unknown Bias or Center";
                const perspective = (pMatch && pMatch[1]) ? pMatch[1].trim() : "Unknown Perspective";
                const context = (cMatch && cMatch[1]) ? cMatch[1].trim() : "Unknown Ommitted Context";
                const link = (lMatch && lMatch[1]) ? lMatch[1].trim() : "#";

                let badgeColor = "#64748b";
                if (bias.includes("Left")) badgeColor = "#ef4444";
                if (bias.includes("Right")) badgeColor = "#3b82f6";

                htmlCardLayout += `
                    <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px;">
                            <span style="font-weight: 700; color: #1e293b; font-size: 14px; text-transform: uppercase; letter-spacing: 0.05em; ">Source ${index+1}: ${source}</span>
                            <span style="background: ${badgeColor}; color: white; padding: 4px 10px; font-size: 12px; font-weight: 600; border-radius: 20px;">${bias}</span>
                        </div>
                            <h4 style="margin: 0 0 12px 0; font-size: 16px; color: #000000; font-weight: 600;">${title}</h4>

                            <p style="margin: 0 0 8px 0; font-size: 14px;"><strong style="color: #475569;">Framing & Perspective:</strong> ${perspective}</p>
                            <p style="margin: 0; font-size: 14px;"><strong style="color: #475569;">Ommitted Context:</strong> ${context}</p>
                        <div style="margin-top: 15px; border-top: 1px dashed #e2e8f0; padding-top: 12px;">
                            <a href="${link}" target="_blank" rel="noopener noreferrer" style="color: #2563eb; font-weight: 600; text-decoration: none; font-size: 14px;">
                                Read Original Article &rarr;
                            </a>
                        </div>
                    </div>
                `;
            });

            htmlCardLayout += `</div>`
            outputText.innerHTML = htmlCardLayout;

            localStorage.setItem("savedMediaReport", htmlCardLayout);
            localStorage.setItem("savedMediaTopic", inputText);
        } else if (data && data.detail) {
            outputText.innerText = JSON.stringify(data.detail);
        } else {
            outputText.innerText = JSON.stringify(data);
        }
    } catch(error) {
        outputText.innerText = "Crash: " + error.message;
        console.error(error);
    }
}

function clearDashboard() {
    document.getElementById("promptInput").value = "";
    document.getElementById("promptOutput").innerText = "Your report...";

    localStorage.removeItem("savedMediaReport");
    localStorage.removeItem("savedMediaTopic");
}

document.getElementById("promptInput").addEventListener('keydown', function(event) {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendPrompt();
    }
});
