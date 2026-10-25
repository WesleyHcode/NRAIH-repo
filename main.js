async function sendPrompt() {
    const inputText = document.getElementById("promptInput").value;
    const outputText = document.getElementById("promptOutput");

    outputText.innerText = "Loading";

    try {
        const response = await fetch("http://127.0.0.1:8000/api/chat", 
            {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({prompt: inputText})
            }
        );
        const data = await response.json();
        if (data && data.response) {
            outputText.innerText = data.response
        } else if (data && data.detail) {
            outputText.innerText = JSON.stringify(data.detail);
        } else {
            outputText.innerText = JSON.stringify(data);
        }
    } catch(error) {
        outputText.innerText = "Error";
        print("str{(e)}");
        console.error(error);
    }
}