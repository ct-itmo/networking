document.addEventListener("DOMContentLoaded", function() {
    const tracked = [];
    ace.config.set("workerPath", "https://cdnjs.cloudflare.com/ajax/libs/ace/1.4.12/");

    function fillAreas() {
        for (const { editor, textarea } of tracked) {
            textarea.value = editor.getValue();
        }
    }

    for (const form of document.querySelectorAll('form')) {
        form.addEventListener('submit', fillAreas);
    }

    for (const el of document.querySelectorAll('.ace')) {
        const shortId = el.id.slice(0, -4);
        el.style.display = 'block';
        el.style.height = '200px';

        const textarea = document.querySelector(`#${shortId}`);
        textarea.style.display = 'none';
        textarea.required = false;

        const editor = ace.edit(el);
        editor.session.setOptions({
            indentedSoftWrap: false,
            tabSize: 2,
            useSoftTabs: true
        });
        editor.session.setUseWrapMode(true);
        if (textarea.dataset.mode) {
            editor.session.setMode(`ace/mode/${textarea.dataset.mode}`);
        }
        editor.setOptions({
            fontFamily: "JetBrains Mono",
            fontSize: "14px"
        });

        tracked.push({ editor, textarea });
    }
});
