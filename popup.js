chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
  chrome.scripting.executeScript({
    target: { tabId: tabs[0].id },
    function: () => {
      document.body.childNodes.forEach(child => blurHateSpeech(child));
    }
  });
});

document.getElementById("start").addEventListener("click", () => {
  document.getElementById("output").innerHTML = "Loading text...";
  var output = document.getElementById('output');
  var action = document.getElementById('action');
  let recognition = new webkitSpeechRecognition();

  recognition.onstart = () => {
      action.innerHTML = "Listening...";
  }

  recognition.onresult = (e) => {
      var transcript = e.results[0][0].transcript;
      output.innerHTML = transcript;
      output.classList.remove("hide");
      action.innerHTML = "";

      // Send the transcribed text to the backend
      fetch('http://localhost:5050/transcribe', {
          method: 'POST',
          headers: {
              'Content-Type': 'application/json'
          },
          body: JSON.stringify({ text: transcript })
      })
      .then(response => response.json())
      .then(data => {
          // Display whether hate speech was detected or not
          if (data.text) {
              output.innerHTML += "<br><strong style='color:red;'>Hate speech detected!</strong>";
          } else {
              output.innerHTML += "<br><strong style='color:green;'>No hate speech detected.</strong>";
          }
      })
      .catch(error => {
          console.error("Error:", error);
          output.innerHTML += "<br><strong style='color:orange;'>Error processing the text.</strong>";
      });
  }

  recognition.start();
});
