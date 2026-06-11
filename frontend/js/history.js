window.ResearchGPT.onReady(() => {
    "use strict";

    const {
        apiFetch,
        escapeHTML,
        formatDate,
        isLoggedIn,
        renderMarkdown,
        showToast
    } = window.ResearchGPT;

    if (!isLoggedIn()) {
        return;
    }

    const params = new URLSearchParams(window.location.search);
    const state = {
        tab: params.get("tab") === "search" ? "search" : "chat",
        chats: [],
        searches: []
    };

    const chatTab = document.getElementById("chatTab");
    const searchTab = document.getElementById("searchTab");
    const historySearch = document.getElementById("historySearch");
    const historyList = document.getElementById("historyList");
    const clearSearchHistory = document.getElementById("clearSearchHistory");

    function setActiveTab(tab) {
        state.tab = tab;
        chatTab.classList.toggle("active", tab === "chat");
        searchTab.classList.toggle("active", tab === "search");
        clearSearchHistory.style.display = tab === "search" ? "inline-flex" : "none";
        window.history.replaceState({}, "", `history.html?tab=${tab}`);
        renderHistory();
    }

    function matchesFilter(values) {
        const filter = historySearch.value.trim().toLowerCase();
        if (!filter) {
            return true;
        }
        return values.some((value) => String(value || "").toLowerCase().includes(filter));
    }

    function renderChatHistory() {
        const chats = state.chats.filter((chat) => matchesFilter([chat.question, chat.answer]));

        if (!chats.length) {
            historyList.innerHTML = '<div class="empty-state">No chat history found.</div>';
            return;
        }

        historyList.innerHTML = chats.map((chat) => `
            <article class="data-item">
                <div>
                    <h3>${escapeHTML(chat.question)}</h3>
                    <div class="message-content">${renderMarkdown(chat.answer)}</div>
                    <p>${formatDate(chat.created_at)}</p>
                </div>
            </article>
        `).join("");
    }

    function renderSearchHistory() {
        const searches = state.searches.filter((entry) => matchesFilter([entry.query]));

        if (!searches.length) {
            historyList.innerHTML = '<div class="empty-state">No search history found.</div>';
            return;
        }

        historyList.innerHTML = searches.map((entry) => `
            <article class="data-item">
                <div>
                    <h3>${escapeHTML(entry.query)}</h3>
                    <p>${formatDate(entry.searched_at)}</p>
                </div>
            </article>
        `).join("");
    }

    function renderHistory() {
        if (state.tab === "chat") {
            renderChatHistory();
            return;
        }

        renderSearchHistory();
    }

    async function loadHistory() {
        try {
            historyList.innerHTML = '<div class="empty-state">Loading history...</div>';
            const [chats, searches] = await Promise.all([
                apiFetch("/my-chat-history"),
                apiFetch("/search-history")
            ]);
            state.chats = Array.isArray(chats) ? chats : [];
            state.searches = Array.isArray(searches) ? searches : [];
            setActiveTab(state.tab);
        } catch (error) {
            historyList.innerHTML = '<div class="empty-state">Unable to load history.</div>';
            showToast(error.message, "error");
        }
    }

    chatTab.addEventListener("click", () => setActiveTab("chat"));
    searchTab.addEventListener("click", () => setActiveTab("search"));
    historySearch.addEventListener("input", renderHistory);

    clearSearchHistory.addEventListener("click", async () => {
        if (!window.confirm("Clear all search history?")) {
            return;
        }

        try {
            const response = await apiFetch("/search-history", { method: "DELETE" });
            showToast(response.message || "Search history cleared.", "success");
            await loadHistory();
        } catch (error) {
            showToast(error.message, "error");
        }
    });

    loadHistory();
});
