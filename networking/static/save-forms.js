document.addEventListener("DOMContentLoaded", function() {
    // Debounce helper function
    function debounce(func, wait) {
        let timeout;
        return function(...args) {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), wait);
        };
    }

    // Save form data to localStorage
    function saveFormData(form, input) {
        const formKey = `form-${form.action}`;
        let formData = JSON.parse(localStorage.getItem(formKey) || '{}');
        formData[input.name] = input.value;
        localStorage.setItem(formKey, JSON.stringify(formData));
    }

    // Load form data from localStorage
    function loadFormData(form) {
        const formKey = `form-${form.action}`;
        const formData = JSON.parse(localStorage.getItem(formKey) || '{}');
        
        for (const input of form.querySelectorAll("input[type=text]")) {
            if (formData[input.name]) {
                input.value = formData[input.name];
            }
        }
    }

    // Handle form submissions - clear saved data
    function handleSubmit(event) {
        const form = event.target;
        const formKey = `form-${form.action}`;
        localStorage.removeItem(formKey);
    }

    // Initialize forms
    for (const form of document.querySelectorAll("form[method=post]")) {
        // Load saved data
        loadFormData(form);

        // Add submit handler
        form.addEventListener('submit', handleSubmit);

        // Add input handlers
        for (const input of form.querySelectorAll("input[type=text]")) {
            input.addEventListener('input', debounce(() => {
                saveFormData(form, input);
            }, 500)); // 500ms debounce
        }
    }
});
