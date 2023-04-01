document.addEventListener("DOMContentLoaded", function() {
    for (const form of document.querySelectorAll("form[method=post]")) {
        form.addEventListener("submit", function(ev) {
            if (form.dataset.blocked === "true") {
                ev.preventDefault();
            } else {
                form.dataset.blocked = "true";
                setTimeout(() => { form.dataset.blocked = "false"; }, 5000);
            }
        });
    }
});
