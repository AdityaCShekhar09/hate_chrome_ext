const scannedNodes = new WeakSet();
let scanInProgress = null;

async function detectHateSpeechBatch(texts) {
  try {
    const chunks = [];
    for (let index = 0; index < texts.length; index += 100) {
      chunks.push(texts.slice(index, index + 100));
    }
    const results = await Promise.all(chunks.map(chunk => new Promise((resolve, reject) => {
      chrome.runtime.sendMessage({ type: 'classify-batch', texts: chunk }, response => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
        } else if (!response?.ok || !Array.isArray(response.toxic)) {
          reject(new Error(response?.error || 'Invalid response from background service worker'));
        } else {
          resolve(response.toxic);
        }
      });
    })));
    return results.flat();
  } catch (error) {
    console.error('Error requesting toxicity classification:', error);
    return texts.map(() => false);
  }
}

function blurTextNode(node) {
  const span = document.createElement('span');
  span.textContent = node.textContent;
  span.className = 'toxicity-blurred-text';
  span.dataset.toxicityBlurred = 'true';
  span.style.setProperty('filter', 'blur(6px)', 'important');
  span.style.setProperty('display', 'inline-block', 'important');
  span.style.setProperty('cursor', 'help', 'important');
  span.title = 'Text hidden because it was classified as toxic';
  node.replaceWith(span);
}

async function blurHateSpeech(node) {
  if (node.nodeType === Node.TEXT_NODE) {
    if (node.textContent.trim() && !scannedNodes.has(node)) return [node];
    return [];
  } else if (node.nodeType === Node.ELEMENT_NODE) {
    if (node.dataset.toxicityBlurred === 'true') return [];
    if (['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEXTAREA', 'INPUT'].includes(node.tagName)) return [];
    return (await Promise.all(Array.from(node.childNodes).map(blurHateSpeech))).flat();
  }
  return [];
}

async function processDocumentBody() {
  if (scanInProgress) return scanInProgress;
  scanInProgress = (async () => {
    if (!document.body) {
      setTimeout(processDocumentBody, 250);
      return;
    }
    const nodes = (await Promise.all(Array.from(document.body.childNodes).map(blurHateSpeech))).flat();
    if (!nodes.length) return;
    const toxicResults = await detectHateSpeechBatch(nodes.map(node => node.textContent));
    nodes.forEach((node, index) => {
      scannedNodes.add(node);
      if (toxicResults[index] && node.isConnected) blurTextNode(node);
    });
  })();
  try {
    await scanInProgress;
  } finally {
    scanInProgress = null;
  }
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === 'scan-page') {
    processDocumentBody();
    sendResponse({ ok: true });
  }
  return true;
});

const observer = new MutationObserver((mutations) => {
  const addedNodes = mutations.flatMap(mutation => Array.from(mutation.addedNodes));
  if (addedNodes.length) {
    Promise.all(addedNodes.map(blurHateSpeech)).then(async nestedNodes => {
      const nodes = nestedNodes.flat();
      if (!nodes.length) return;
      const results = await detectHateSpeechBatch(nodes.map(node => node.textContent));
      nodes.forEach((node, index) => {
        scannedNodes.add(node);
        if (results[index] && node.isConnected) blurTextNode(node);
      });
    });
  }
});

processDocumentBody();
observer.observe(document.documentElement, { childList: true, subtree: true });
