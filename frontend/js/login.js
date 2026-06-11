window.ResearchGPT.onReady(() => {
    "use strict";

    const {
        login,
        setButtonLoading,
        setFlash,
        showInlineMessage
    } = window.ResearchGPT;

    const form = document.getElementById("loginForm");
    const message = document.getElementById("loginMessage");

    if (!form) {
        return;
    }

    function safeNext(value) {
        if (!value || value.startsWith("http") || value.startsWith("//")) {
            return "dashboard.html";
        }
        return value;
    }

    const params = new URLSearchParams(window.location.search);
    const username = params.get("username");
    if (username) {
        const usernameInput = form.querySelector('[name="username_or_email"]');
        usernameInput.value = username;
        form.querySelector('[name="password"]').focus();
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();

        const button = form.querySelector('button[type="submit"]');
        const formData = new FormData(form);
        const payload = {
            username_or_email: String(formData.get("username_or_email") || "").trim(),
            password: String(formData.get("password") || "")
        };

        if (!payload.username_or_email || !payload.password) {
            showInlineMessage(message, "Enter both username or email and password.", "error");
            return;
        }

        setButtonLoading(button, true);
        showInlineMessage(message, "Signing in...");

        try {
            await login(payload);
            showInlineMessage(message, "Login successful. Redirecting...", "success");
            setFlash("Logged in successfully.", "success");
            window.location.href = safeNext(params.get("next"));
        } catch (error) {
            showInlineMessage(message, error.message, "error");
        } finally {
            setButtonLoading(button, false);
        }
    });
});
