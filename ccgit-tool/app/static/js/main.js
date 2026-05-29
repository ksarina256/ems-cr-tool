/* CCGit Tool - main.js */

document.addEventListener("DOMContentLoaded", () => {
  const dryRunCheckbox = document.querySelector('input[name="dry_run"]');
  const submitBtn = document.querySelector('button[type="submit"]');

  if (dryRunCheckbox && submitBtn) {
    dryRunCheckbox.addEventListener("change", () => {
      if (dryRunCheckbox.checked) {
        submitBtn.textContent = "Run Dry-Run Preview →";
        submitBtn.style.background = "#e65100";
      } else {
        submitBtn.textContent = "Start Migration →";
        submitBtn.style.background = "";
      }
    });
  }
});
