async function sendPrompt() {
    const inputText = document.getElementById("promptInput").value;
    const outputText = document.getElementById("promptOutput");

    outputText.innerText = "Loading";

    try {
        const response = await fetch("http://127.0.0", 
            {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({prompt: inputText})
            }
        );
        const data = await response.json();
        outputText.innerText = data.response;

    } catch(error) {
        outputText.innerText = "Error";
        console.error(error);
    }
}