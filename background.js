chrome.runtime.onInstalled.addListener(() => {
  console.log("Hate Speech Blur extension installed.");
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type !== 'classify-batch') return false;

  fetch('http://127.0.0.1:5050/detect-batch', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ texts: message.texts })
  })
    .then(async response => {
      if (!response.ok) {
        throw new Error(`Backend returned ${response.status}`);
      }
      return response.json();
    })
    .then(result => sendResponse({ ok: true, toxic: result.toxic }))
    .catch(error => {
      console.error('Could not reach toxicity backend:', error);
      sendResponse({
        ok: false,
        error: 'Toxicity backend is unavailable. Start Docker and try again.'
      });
    });

  return true;
});
