document.addEventListener("DOMContentLoaded", function () {
    const table = document.querySelector("table.exam-grade");
    if (!table) return;

    const saveUrl = table.dataset.saveUrl;
    const csrfInput = document.querySelector('input[name="csrf_token"]');
    const csrf = csrfInput ? csrfInput.value : "";

    const inputs = Array.from(table.querySelectorAll("input.grade-input"));

    async function save(input) {
        const row = input.closest("tr");
        const status = row.querySelector(".grade-status");

        const body = new FormData();
        body.append("csrf_token", csrf);
        body.append("user_id", row.dataset.userId);
        body.append("points", input.value);

        status.textContent = "…";
        status.className = "grade-status";

        try {
            const resp = await fetch(saveUrl, {
                method: "POST",
                body: body,
                headers: { "X-Requested-With": "fetch" },
            });
            const data = await resp.json();
            if (data.ok) {
                status.textContent = "✔";
                status.className = "grade-status saved";
            } else {
                status.textContent = "✖";
                status.className = "grade-status error";
            }
        } catch (e) {
            status.textContent = "✖";
            status.className = "grade-status error";
        }
    }

    inputs.forEach(function (input, idx) {
        input.addEventListener("keydown", function (ev) {
            if (ev.key === "Enter") {
                ev.preventDefault();
                save(input);
                const next = inputs[idx + 1];
                if (next) {
                    next.focus();
                    next.select();
                }
            }
        });
        // also persist if the teacher clicks away after typing
        input.addEventListener("change", function () {
            save(input);
        });
    });
});
