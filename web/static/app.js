document.addEventListener("submit", function (event) {
  const form = event.target;
  const message = form.getAttribute("data-confirm");
  if (message && !window.confirm(message)) {
    event.preventDefault();
  }
});

document.addEventListener("click", function (event) {
  const button = event.target.closest("[data-copy-text]");
  if (!button) {
    return;
  }
  const value = button.getAttribute("data-copy-text") || "";
  navigator.clipboard.writeText(value).then(function () {
    const original = button.textContent;
    button.textContent = "Скопировано";
    window.setTimeout(function () {
      button.textContent = original;
    }, 1200);
  });
});
