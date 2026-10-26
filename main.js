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

async function sendPrompt() {
    const inputText = document.getElementById("promptInput").value;
    const outputText = document.getElementById("promptOutput");

    if (!inputText.trim()) {
        outputText.innerText = "Please enter a news topic first"
        return;
    }

    outputText.innerText = "Loading";

    try {
        const response = await fetch("http://127.0.0.1:8000/api/analyze-topic", 
            {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({topic: inputText})
            }
        );

        const data = await response.json();
        
        if (data && data.response) {
            const parsedData = JSON.parse(data.response);
            const analysesArray = parsedData.analyses;

            if (!analysesArray || analysesArray.length === 0) {
                outputText.innerText = "No analyses available";
                return;
            }

            let htmlCardLayout = '<div style="display: flex; flex-direction: column; gap: 20px;">';

            analysesArray.forEach((article, index) => {
                let badgeColor = "#64748b";
                if (article.bias_rating.includes("Left")) badgeColor = "#ef4444";
                if (article.bias_rating.includes("Right")) badgeColor = "#3b82f6";

                htmlCardLayout += `
                    <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px;">
                            <span style="font-weight: 700; color: #1e293b; font-size: 14px; text-transform: uppercase; letter-spacing: 0.05em; ">Source ${index+1}: ${article.source}</span>
                            <span style="background: ${badgeColor}; color: white; padding: 4px 10px; font-size: 12px; font-weight: 600; border-radius: 20px;">${article.bias_rating}</span>
                        </div>
                            <h4 style="margin: 0 0 12px 0; font-size: 16px; color: #000000; font-weight: 600;">${article.title}</h4>

                            <p style="margin: 0 0 8px 0; font-size: 14px;"><strong style="color: #475569;">Framing & Perspective:</strong> ${article.dominant_perspective}</p>
                            <p style="margin: 0; font-size: 14px;"><strong style="color: #475569;">Ommitted Context:</strong> ${article.omitted_context}</p>
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
        outputText.innerText = "Error";
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
