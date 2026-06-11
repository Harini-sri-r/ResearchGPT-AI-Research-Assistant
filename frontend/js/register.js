window.ResearchGPT.onReady(() => {
    "use strict";

    const {
        register,
        setButtonLoading,
        setFlash,
        showInlineMessage
    } = window.ResearchGPT;

    const form = document.getElementById("registerForm");
    const message = document.getElementById("registerMessage");
    const emailPattern = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
    const usernamePattern = /^[A-Za-z0-9_]{3,100}$/;

    if (!form) {
        return;
    }

    function validate(payload) {
        if (!usernamePattern.test(payload.username)) {
            return "Username must be 3-100 characters and use only letters, numbers, or underscores.";
        }
        if (!emailPattern.test(payload.email)) {
            return "Enter a valid email address.";
        }
        if (payload.password.length < 8) {
            return "Password must be at least 8 characters.";
        }
        if (payload.password.trim() !== payload.password) {
            return "Password cannot start or end with spaces.";
        }
        if (!/[a-z]/.test(payload.password) || !/[A-Z]/.test(payload.password) || !/\d/.test(payload.password)) {
            return "Password must contain lowercase, uppercase, and a number.";
        }
        return "";
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();

        const button = form.querySelector('button[type="submit"]');
        const formData = new FormData(form);
        const payload = {
            username: String(formData.get("username") || "").trim(),
            email: String(formData.get("email") || "").trim().toLowerCase(),
            password: String(formData.get("password") || "")
        };
        const validationMessage = validate(payload);

        if (validationMessage) {
            showInlineMessage(message, validationMessage, "error");
            return;
        }

        setButtonLoading(button, true);
        showInlineMessage(message, "Creating account...");

        try {
            await register(payload);
            showInlineMessage(message, "Registration successful. Opening login...", "success");
            setFlash("Account created successfully. Please log in.", "success");
            window.setTimeout(() => {
                window.location.href = `login.html?username=${encodeURIComponent(payload.username)}`;
            }, 450);
        } catch (error) {
            showInlineMessage(message, error.message, "error");
        } finally {
            setButtonLoading(button, false);
        }
    });
});
