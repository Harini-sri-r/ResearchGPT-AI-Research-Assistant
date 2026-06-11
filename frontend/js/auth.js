(function () {
    "use strict";

    const api = window.ResearchGPTApi;
    const USER_KEY = "researchgpt_user";
    const THEME_KEY = "researchgpt_theme";
    const FLASH_KEY = "researchgpt_flash";

    const icons = {
        sun: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="4"></circle><path d="M12 2v2"></path><path d="M12 20v2"></path><path d="m4.93 4.93 1.41 1.41"></path><path d="m17.66 17.66 1.41 1.41"></path><path d="M2 12h2"></path><path d="M20 12h2"></path><path d="m6.34 17.66-1.41 1.41"></path><path d="m19.07 4.93-1.41 1.41"></path></svg>',
        moon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3a6 6 0 0 0 9 7 9 9 0 1 1-9-7Z"></path></svg>',
        copy: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect width="14" height="14" x="8" y="8" rx="2"></rect><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"></path></svg>'
    };

    let readyResolve;
    const ready = new Promise((resolve) => {
        readyResolve = resolve;
    });

    function saveToken(tokenOrPayload, user) {
        const token = typeof tokenOrPayload === "string"
            ? tokenOrPayload
            : tokenOrPayload && tokenOrPayload.access_token;

        if (!token) {
            throw new Error("Login response did not include a JWT token.");
        }

        api.setAccessToken(token);

        const resolvedUser = user || (tokenOrPayload && tokenOrPayload.user);
        if (resolvedUser) {
            saveUser(resolvedUser);
        }
    }

    function saveUser(user) {
        if (!user) {
            return;
        }
        localStorage.setItem(USER_KEY, JSON.stringify(user));
    }

    function getToken() {
        return api.getAccessToken();
    }

    function getUser() {
        try {
            return JSON.parse(localStorage.getItem(USER_KEY) || "null");
        } catch (error) {
            localStorage.removeItem(USER_KEY);
            return null;
        }
    }

    function clearSession() {
        api.clearAccessToken();
        localStorage.removeItem(USER_KEY);
    }

    function removeToken() {
        clearSession();
    }

    function isLoggedIn() {
        return Boolean(getToken());
    }

    function currentPageName() {
        const page = window.location.pathname.split("/").pop();
        return page || "index.html";
    }

    function redirectToLogin() {
        if (currentPageName() === "login.html") {
            return;
        }

        const next = encodeURIComponent(currentPageName() + window.location.search);
        window.location.replace(`login.html?next=${next}`);
    }

    function redirectToDashboard() {
        if (currentPageName() !== "dashboard.html") {
            window.location.replace("dashboard.html");
        }
    }

    function setFlash(message, type = "info") {
        if (!message) {
            return;
        }

        sessionStorage.setItem(FLASH_KEY, JSON.stringify({ message, type }));
    }

    function consumeFlash() {
        const rawFlash = sessionStorage.getItem(FLASH_KEY);
        if (!rawFlash) {
            return;
        }

        sessionStorage.removeItem(FLASH_KEY);

        try {
            const flash = JSON.parse(rawFlash);
            showToast(flash.message, flash.type || "info");
        } catch (error) {
            showToast(rawFlash);
        }
    }

    async function validateSession(options = {}) {
        const redirectOnFailure = Boolean(options.redirectOnFailure);

        if (!getToken()) {
            clearSession();
            if (redirectOnFailure) {
                redirectToLogin();
            }
            return null;
        }

        try {
            const user = await api.apiFetch("/me", {}, { skipUnauthorizedHandler: true });
            saveUser(user);
            return user;
        } catch (error) {
            if (error.status === 401 || error.status === 403) {
                clearSession();
                if (redirectOnFailure) {
                    setFlash("Your session expired. Please log in again.", "warning");
                    redirectToLogin();
                }
                return null;
            }

            showToast(error.message, "error");
            return getUser();
        }
    }

    async function login(payload) {
        const response = await api.apiFetch("/login", {
            method: "POST",
            body: payload
        }, { auth: false });

        saveToken(response);
        return response;
    }

    async function register(payload) {
        return api.apiFetch("/register", {
            method: "POST",
            body: payload
        }, { auth: false });
    }

    async function logout() {
        const token = getToken();

        try {
            if (token) {
                await api.apiFetch("/logout", { method: "POST" }, { skipUnauthorizedHandler: true });
            }
            setFlash("Logged out successfully.", "success");
        } catch (error) {
            setFlash("You have been logged out locally.", "warning");
        } finally {
            clearSession();
            window.location.href = "login.html";
        }
    }

    function escapeHTML(value) {
        return String(value || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function renderMarkdown(value) {
        const codeBlocks = [];
        let text = String(value || "").replace(/```([\s\S]*?)```/g, (_, code) => {
            const index = codeBlocks.length;
            codeBlocks.push(`<pre><code>${escapeHTML(code.trim())}</code></pre>`);
            return `@@CODEBLOCK_${index}@@`;
        });

        text = escapeHTML(text)
            .replace(/^### (.+)$/gm, "<h3>$1</h3>")
            .replace(/^## (.+)$/gm, "<h2>$1</h2>")
            .replace(/^# (.+)$/gm, "<h2>$1</h2>")
            .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
            .replace(/`([^`]+)`/g, "<code>$1</code>");

        const blocks = text.split(/\n{2,}/).map((block) => {
            const trimmed = block.trim();
            if (!trimmed) {
                return "";
            }
            if (trimmed.startsWith("@@CODEBLOCK_") || /^<h[23]>/.test(trimmed)) {
                return trimmed;
            }
            if (/^[-*]\s+/m.test(trimmed)) {
                const items = trimmed
                    .split(/\n/)
                    .map((line) => line.replace(/^[-*]\s+/, "").trim())
                    .filter(Boolean)
                    .map((line) => `<li>${line}</li>`)
                    .join("");
                return `<ul>${items}</ul>`;
            }
            return `<p>${trimmed.replace(/\n/g, "<br>")}</p>`;
        });

        return blocks.join("").replace(/@@CODEBLOCK_(\d+)@@/g, (_, index) => codeBlocks[Number(index)] || "");
    }

    function formatDate(value) {
        if (!value) {
            return "-";
        }

        const date = new Date(value);
        if (Number.isNaN(date.getTime())) {
            return "-";
        }

        return new Intl.DateTimeFormat(undefined, {
            year: "numeric",
            month: "short",
            day: "2-digit",
            hour: "2-digit",
            minute: "2-digit"
        }).format(date);
    }

    function showInlineMessage(element, message, type = "info") {
        if (!element) {
            return;
        }

        element.textContent = message || "";
        element.classList.remove("success", "error", "warning");
        if (type !== "info") {
            element.classList.add(type);
        }
    }

    function ensureToastHost() {
        let host = document.querySelector(".toast-host");
        if (!host) {
            host = document.createElement("div");
            host.className = "toast-host";
            document.body.appendChild(host);
        }
        return host;
    }

    function showToast(message, type = "info") {
        if (!message) {
            return;
        }

        const host = ensureToastHost();
        const toast = document.createElement("div");
        toast.className = `toast ${type}`;
        toast.textContent = message;
        host.appendChild(toast);

        window.setTimeout(() => {
            toast.remove();
        }, 4200);
    }

    function setButtonLoading(button, isLoading) {
        if (!button) {
            return;
        }

        button.disabled = isLoading;
        button.classList.toggle("is-loading", isLoading);

        const label = button.querySelector(".button-label");
        if (!label) {
            return;
        }

        if (!button.dataset.defaultLabel) {
            button.dataset.defaultLabel = label.textContent;
        }

        label.textContent = isLoading
            ? button.dataset.loadingLabel || button.dataset.defaultLabel
            : button.dataset.defaultLabel;
    }

    async function copyText(value) {
        if (navigator.clipboard && window.isSecureContext) {
            await navigator.clipboard.writeText(value);
            return;
        }

        const area = document.createElement("textarea");
        area.value = value;
        area.style.position = "fixed";
        area.style.opacity = "0";
        document.body.appendChild(area);
        area.select();
        document.execCommand("copy");
        area.remove();
    }

    function setTheme(theme) {
        const resolvedTheme = theme === "dark" ? "dark" : "light";
        document.documentElement.dataset.theme = resolvedTheme;
        localStorage.setItem(THEME_KEY, resolvedTheme);

        document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
            button.innerHTML = resolvedTheme === "dark" ? icons.sun : icons.moon;
            button.setAttribute(
                "aria-label",
                resolvedTheme === "dark" ? "Switch to light mode" : "Switch to dark mode"
            );
            button.title = resolvedTheme === "dark" ? "Light mode" : "Dark mode";
        });
    }

    function initTheme() {
        const savedTheme = localStorage.getItem(THEME_KEY);
        const preferredTheme = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
        setTheme(savedTheme || preferredTheme);
    }

    function bindGlobalControls() {
        document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
            button.addEventListener("click", () => {
                const nextTheme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
                setTheme(nextTheme);
            });
        });

        document.querySelectorAll("[data-logout]").forEach((button) => {
            button.addEventListener("click", (event) => {
                event.preventDefault();
                logout();
            });
        });

        document.querySelectorAll("[data-auth-link]").forEach((link) => {
            if (isLoggedIn()) {
                link.href = "dashboard.html";
                link.textContent = "Open dashboard";
            }
        });
    }

    function initHeroCanvas() {
        const canvas = document.getElementById("heroCanvas");
        if (!canvas) {
            return;
        }

        const context = canvas.getContext("2d");
        const pointer = { x: 0.55, y: 0.42 };
        const nodes = Array.from({ length: 28 }, (_, index) => ({
            x: 0.42 + ((index * 37) % 50) / 100,
            y: 0.12 + ((index * 53) % 74) / 100,
            r: 2 + (index % 4),
            phase: index * 0.42
        }));

        function resize() {
            const dpr = Math.min(window.devicePixelRatio || 1, 2);
            canvas.width = Math.floor(canvas.clientWidth * dpr);
            canvas.height = Math.floor(canvas.clientHeight * dpr);
            context.setTransform(dpr, 0, 0, dpr, 0, 0);
        }

        function roundedRectPath(x, y, width, height, radius) {
            const safeRadius = Math.min(radius, width / 2, height / 2);
            context.beginPath();
            context.moveTo(x + safeRadius, y);
            context.lineTo(x + width - safeRadius, y);
            context.quadraticCurveTo(x + width, y, x + width, y + safeRadius);
            context.lineTo(x + width, y + height - safeRadius);
            context.quadraticCurveTo(x + width, y + height, x + width - safeRadius, y + height);
            context.lineTo(x + safeRadius, y + height);
            context.quadraticCurveTo(x, y + height, x, y + height - safeRadius);
            context.lineTo(x, y + safeRadius);
            context.quadraticCurveTo(x, y, x + safeRadius, y);
            context.closePath();
        }

        function drawPaper(x, y, width, height, rotation, fill, stroke) {
            context.save();
            context.translate(x, y);
            context.rotate(rotation);
            context.fillStyle = fill;
            context.strokeStyle = stroke;
            context.lineWidth = 1;
            roundedRectPath(-width / 2, -height / 2, width, height, 8);
            context.fill();
            context.stroke();

            context.fillStyle = "rgba(17, 24, 39, 0.32)";
            for (let i = 0; i < 5; i += 1) {
                context.fillRect(-width / 2 + 18, -height / 2 + 24 + i * 18, width - 36 - i * 9, 3);
            }
            context.restore();
        }

        function draw(time) {
            const width = canvas.clientWidth;
            const height = canvas.clientHeight;
            const shiftX = (pointer.x - 0.5) * 30;
            const shiftY = (pointer.y - 0.5) * 22;

            context.clearRect(0, 0, width, height);

            context.strokeStyle = "rgba(255, 255, 255, 0.055)";
            context.lineWidth = 1;
            for (let x = 0; x < width; x += 64) {
                context.beginPath();
                context.moveTo(x + shiftX * 0.25, 0);
                context.lineTo(x - shiftX * 0.25, height);
                context.stroke();
            }
            for (let y = 0; y < height; y += 64) {
                context.beginPath();
                context.moveTo(0, y + shiftY * 0.2);
                context.lineTo(width, y - shiftY * 0.2);
                context.stroke();
            }

            context.strokeStyle = "rgba(56, 196, 167, 0.26)";
            nodes.forEach((node, index) => {
                const x = node.x * width + Math.sin(time * 0.001 + node.phase) * 10 + shiftX;
                const y = node.y * height + Math.cos(time * 0.0012 + node.phase) * 8 + shiftY;

                if (index > 0 && index % 3 !== 0) {
                    const previous = nodes[index - 1];
                    context.beginPath();
                    context.moveTo(previous.x * width + shiftX, previous.y * height + shiftY);
                    context.lineTo(x, y);
                    context.stroke();
                }

                context.fillStyle = index % 5 === 0 ? "rgba(243, 182, 75, 0.88)" : "rgba(56, 196, 167, 0.82)";
                context.beginPath();
                context.arc(x, y, node.r, 0, Math.PI * 2);
                context.fill();
            });

            drawPaper(width * 0.68 + shiftX, height * 0.34 + shiftY, 180, 230, -0.16, "rgba(255,255,255,0.78)", "rgba(255,255,255,0.42)");
            drawPaper(width * 0.82 + shiftX * 1.2, height * 0.48 + shiftY, 150, 196, 0.15, "rgba(241,245,249,0.66)", "rgba(255,255,255,0.36)");
            drawPaper(width * 0.58 + shiftX * 0.8, height * 0.62 + shiftY, 142, 178, 0.08, "rgba(255,255,255,0.58)", "rgba(255,255,255,0.28)");

            context.fillStyle = "rgba(17, 24, 39, 0.58)";
            context.strokeStyle = "rgba(255, 255, 255, 0.18)";
            roundedRectPath(width * 0.56 + shiftX, height * 0.18 + shiftY, 280, 86, 8);
            context.fill();
            context.stroke();

            context.fillStyle = "rgba(56, 196, 167, 0.7)";
            context.fillRect(width * 0.58 + shiftX, height * 0.21 + shiftY, 132, 5);
            context.fillStyle = "rgba(255, 255, 255, 0.38)";
            context.fillRect(width * 0.58 + shiftX, height * 0.25 + shiftY, 220, 4);
            context.fillRect(width * 0.58 + shiftX, height * 0.29 + shiftY, 176, 4);

            window.requestAnimationFrame(draw);
        }

        canvas.addEventListener("pointermove", (event) => {
            const rect = canvas.getBoundingClientRect();
            pointer.x = (event.clientX - rect.left) / rect.width;
            pointer.y = (event.clientY - rect.top) / rect.height;
        });

        window.addEventListener("resize", resize);
        resize();
        window.requestAnimationFrame(draw);
    }

    function onUnauthorized() {
        clearSession();
        setFlash("Your session expired. Please log in again.", "warning");
        redirectToLogin();
    }

    function onReady(callback) {
        ready.then(callback).catch((error) => {
            showToast(error.message || "Unable to initialize the page.", "error");
        });
    }

    async function boot() {
        initTheme();
        bindGlobalControls();
        initHeroCanvas();
        consumeFlash();

        const isProtected = document.body.dataset.authRequired === "true";
        const isGuestOnly = document.body.dataset.guestOnly === "true";

        if (isProtected) {
            const user = await validateSession({ redirectOnFailure: true });
            readyResolve(user);
            return;
        }

        if (isGuestOnly && getToken()) {
            const user = await validateSession({ redirectOnFailure: false });
            if (user) {
                redirectToDashboard();
                readyResolve(user);
                return;
            }
        }

        readyResolve(getUser());
    }

    api.setUnauthorizedHandler(onUnauthorized);

    window.ResearchGPT = {
        ...(window.ResearchGPT || {}),
        API_BASE: api.API_BASE,
        apiFetch: api.apiFetch,
        buildApiUrl: api.buildApiUrl,
        clearSession,
        copyText,
        escapeHTML,
        extractApiMessage: api.extractApiMessage,
        formatDate,
        getToken,
        getUser,
        icon: (name) => icons[name] || "",
        isLoggedIn,
        login,
        logout,
        onReady,
        ready,
        register,
        removeToken,
        renderMarkdown,
        saveToken,
        saveUser,
        setButtonLoading,
        setFlash,
        showInlineMessage,
        showToast,
        uploadWithProgress: api.uploadWithProgress,
        validateSession
    };

    document.addEventListener("DOMContentLoaded", boot);
})();
