async function detectHateSpeech(text) {
  try {
    const response = await fetch('http://127.0.0.1:5050/detect', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text })
    });

    if (!response.ok) {
      console.error('Failed to fetch:', response.statusText);
      return false;
    }

    const result = await response.json();
    return result.toxic;
  } catch (error) {
    console.error('Error detecting hate speech:', error);
    return false;
  }
}

function blurTextNode(node) {
  const span = document.createElement('span');
  span.textContent = node.textContent;
  span.style.filter = 'blur(5px)';
  node.replaceWith(span);
}

async function blurHateSpeech(node) {
  if (node.nodeType === Node.TEXT_NODE) {
    const isToxic = await detectHateSpeech(node.textContent);
    if (isToxic) {
      blurTextNode(node);
    }
  } else if (node.nodeType === Node.ELEMENT_NODE) {
    for (const child of Array.from(node.childNodes)) {
      await blurHateSpeech(child);
    }
  }
}

async function processDocumentBody() {
  for (const child of Array.from(document.body.childNodes)) {
    await blurHateSpeech(child);
  }
}

processDocumentBody();
