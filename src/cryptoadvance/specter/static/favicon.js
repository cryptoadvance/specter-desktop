// Only run this code if the browser is supporting the matchMedia API
if (window.matchMedia) {
  let favicon = document.getElementById('favicon');
  // Set the initial favicon based on the color scheme preference
  if (matchMedia('(prefers-color-scheme: dark)').matches) {
    favicon.href = '/static/img/favicon-dark-mode.png';
  } 
  else {
    favicon.href = '/static/img/favicon-light-mode.png';
  }
  // Listen for changes in the color scheme preference and update the favicon accordingly
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function(e) {
    if (e.matches) {
      favicon.href = '/static/img/favicon-dark-mode.png';
    } 
    else {
      favicon.href = '/static/img/favicon-light-mode.png';
    }
  });
}


