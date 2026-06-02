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

document.addEventListener("click", function (event) {
  const toggle = event.target.closest("[data-sidebar-toggle]");
  const backdrop = event.target.closest("[data-sidebar-backdrop]");
  const mobileLink = event.target.closest("[data-sidebar] .sidebar-link");
  const sidebar = document.querySelector("[data-sidebar]");
  const sidebarBackdrop = document.querySelector("[data-sidebar-backdrop]");

  if (!sidebar || !sidebarBackdrop) {
    return;
  }

  if (toggle) {
    sidebar.classList.toggle("show");
    sidebarBackdrop.classList.toggle("show");
    document.body.classList.toggle("sidebar-open", sidebar.classList.contains("show"));
    return;
  }

  if (backdrop || (mobileLink && window.innerWidth < 992)) {
    sidebar.classList.remove("show");
    sidebarBackdrop.classList.remove("show");
    document.body.classList.remove("sidebar-open");
  }
});
