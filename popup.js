chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
  if (!tabs[0]?.id) return;
  chrome.tabs.sendMessage(tabs[0].id, { type: 'scan-page' }, (response) => {
    const status = document.getElementById('status');
    if (chrome.runtime.lastError) {
      status.textContent = 'Open a normal webpage and reload it to scan.';
    } else if (response?.ok) {
      status.textContent = 'Scan started.';
    }
  });
});
