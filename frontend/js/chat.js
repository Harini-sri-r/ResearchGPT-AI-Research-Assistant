(function () {
    "use strict";

    let controller = null;

    function helpers() {
        return window.ResearchGPT;
    }

    function buildMessage(role, text, options = {}) {
        const {
            copyText,
            escapeHTML,
            formatDate,
            renderMarkdown,
            showToast
        } = helpers();

        const row = document.createElement("article");
        row.className = `message-row ${role}`;

        const bubble = document.createElement("div");
        bubble.className = "message-bubble";

        const meta = document.createElement("div");
        meta.className = "message-meta";

        const label = document.createElement("span");
        label.textContent = role === "user" ? "You" : "ResearchGPT";
        meta.appendChild(label);

        if (role === "assistant" && !options.loading) {
            const copyButton = document.createElement("button");
            copyButton.className = "button button-ghost copy-answer";
            copyButton.type = "button";
            copyButton.innerHTML = `${helpers().icon("copy")} Copy`;
            copyButton.addEventListener("click", async () => {
                await copyText(text);
                showToast("Copied answer.", "success");
            });
            meta.appendChild(copyButton);
        } else if (options.time) {
            const time = document.createElement("time");
            time.textContent = formatDate(options.time);
            meta.appendChild(time);
        }

        const content = document.createElement("div");
        content.className = "message-content";

        if (options.loading) {
            content.innerHTML = '<span class="typing"><span></span><span></span><span></span></span>';
        } else if (role === "assistant") {
            content.innerHTML = renderMarkdown(text);
        } else {
            content.innerHTML = escapeHTML(text).replace(/\n/g, "<br>");
        }

        bubble.append(meta, content);
        row.appendChild(bubble);
        return row;
    }

    function scrollToBottom(messagesElement) {
        messagesElement.scrollTop = messagesElement.scrollHeight;
    }

    function appendMessage(messagesElement, role, text, options = {}) {
        const row = buildMessage(role, text, options);
        messagesElement.appendChild(row);
        scrollToBottom(messagesElement);
        return row;
    }

    function renderHistory(chats = [], options = {}) {
        if (!controller || !controller.messagesElement) {
            return;
        }

        const limit = options.limit || controller.historyLimit || 5;
        const recentChats = chats.slice(0, limit).reverse();
        controller.messagesElement.innerHTML = "";

        if (recentChats.length === 0) {
            appendMessage(controller.messagesElement, "assistant", "Ready for your next research question.");
            return;
        }

        recentChats.forEach((chat) => {
            appendMessage(controller.messagesElement, "user", chat.question, { time: chat.created_at });
            appendMessage(controller.messagesElement, "assistant", chat.answer, { time: chat.created_at });
        });
    }

    async function sendQuestion(question, submitButton) {
        const {
            apiFetch,
            setButtonLoading,
            showToast
        } = helpers();

        const trimmedQuestion = question.trim();
        if (!trimmedQuestion || !controller) {
            return null;
        }

        appendMessage(controller.messagesElement, "user", trimmedQuestion);
        const loadingRow = appendMessage(controller.messagesElement, "assistant", "", { loading: true });
        setButtonLoading(submitButton, true);

        try {
            const response = await apiFetch("/ask", {}, {
                params: { question: trimmedQuestion }
            });
            const answer = response && response.answer ? response.answer : "No answer returned.";
            loadingRow.replaceWith(buildMessage("assistant", answer));
            scrollToBottom(controller.messagesElement);

            if (typeof controller.onAfterSend === "function") {
                await controller.onAfterSend({ question: trimmedQuestion, answer });
            }

            return answer;
        } catch (error) {
            loadingRow.replaceWith(buildMessage("assistant", error.message));
            scrollToBottom(controller.messagesElement);
            showToast(error.message, "error");
            return null;
        } finally {
            setButtonLoading(submitButton, false);
            controller.inputElement.focus();
        }
    }

    function initChat(options = {}) {
        const messagesElement = options.messagesElement || document.querySelector(options.messagesSelector || "#chatMessages");
        const formElement = options.formElement || document.querySelector(options.formSelector || "#chatForm");
        const inputElement = options.inputElement || document.querySelector(options.inputSelector || "#questionInput");

        if (!messagesElement || !formElement || !inputElement) {
            return null;
        }

        controller = {
            formElement,
            historyLimit: options.historyLimit || 5,
            inputElement,
            messagesElement,
            onAfterSend: options.onAfterSend
        };

        formElement.addEventListener("submit", (event) => {
            event.preventDefault();
            const question = inputElement.value.trim();
            if (!question) {
                return;
            }

            inputElement.value = "";
            sendQuestion(question, formElement.querySelector('button[type="submit"]'));
        });

        inputElement.addEventListener("keydown", (event) => {
            if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                formElement.requestSubmit();
            }
        });

        return controller;
    }

    window.ResearchGPTChat = {
        appendMessage: (role, text, options = {}) => {
            if (!controller) {
                return null;
            }
            return appendMessage(controller.messagesElement, role, text, options);
        },
        buildMessage,
        initChat,
        renderHistory,
        sendQuestion
    };
})();
