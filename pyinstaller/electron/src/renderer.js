// This file is required by the index.html file and will
// be executed in the renderer process for that window.
// No Node.js APIs are available in this process because
// `nodeIntegration` is turned off. Use `preload.js` to
// selectively enable features needed in the rendering
// process.

// All of the Node.js APIs are available in the preload process.
// It has the same sandbox as a Chrome extension.
window.addEventListener('DOMContentLoaded', () => {

  
    const updateSpinner = (show) => {
      const spinnerElement = document.getElementById('spinner');
      if (spinnerElement) {
          spinnerElement.classList.toggle('hidden', !show);
      }
    };
    window.api.receive('update-loader-message', (data) => {
      const launchTextElement = document.getElementById('launch-text');
      if (launchTextElement) {
          launchTextElement.textContent = data.msg;
          updateSpinner(data.showSpinner);
      }
    });
  

  })