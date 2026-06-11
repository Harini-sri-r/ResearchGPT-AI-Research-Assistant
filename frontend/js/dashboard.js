window.ResearchGPT.onReady(() => {
    "use strict";

    const {
        apiFetch,
        escapeHTML,
        formatDate,
        getUser,
        saveUser,
        showToast
    } = window.ResearchGPT;

    if (!window.ResearchGPT.isLoggedIn()) {
        return;
    }

    const state = {
        profile: getUser(),
        papers: [],
        chats: [],
        searches: [],
        queryLogs: [],
        favorites: []
    };

    const welcomeTitle = document.getElementById("welcomeTitle");
    const dashboardEmail = document.getElementById("dashboardEmail");
    const welcomeMessage = document.getElementById("welcomeMessage");
    const papersCount = document.getElementById("papersCount");
    const chatsCount = document.getElementById("chatsCount");
    const favoritesCount = document.getElementById("favoritesCount");
    const searchesCount = document.getElementById("searchesCount");
    const queryLogsCount = document.getElementById("queryLogsCount");
    const dashboardPapers = document.getElementById("dashboardPapers");
    const dashboardFavorites = document.getElementById("dashboardFavorites");
    const dashboardSearches = document.getElementById("dashboardSearches");
    const dashboardQueryLogs = document.getElementById("dashboardQueryLogs");
    const focusChat = document.getElementById("focusChat");
    const refreshHistory = document.getElementById("refreshHistory");
    const refreshDashboardData = document.getElementById("refreshDashboardData");
    const questionInput = document.getElementById("questionInput");

    function firstName(username) {
        return String(username || "researcher").split(/\s+/)[0];
    }

    function updateProfileSummary() {
        const user = state.profile || {};
        const username = user.username || "researcher";

        if (welcomeTitle) {
            welcomeTitle.textContent = `Hello ${firstName(username)}`;
        }

        if (dashboardEmail) {
            dashboardEmail.textContent = user.email || "";
        }

        if (welcomeMessage) {
            welcomeMessage.textContent = `Welcome back, ${username}. Your research workspace is ready.`;
        }
    }

    function updateStats() {
        updateProfileSummary();
        papersCount.textContent = state.papers.length;
        chatsCount.textContent = state.chats.length;
        favoritesCount.textContent = state.favorites.length;
        searchesCount.textContent = state.searches.length;

        if (queryLogsCount) {
            queryLogsCount.textContent = state.queryLogs.length;
        }
    }

    function renderList(container, items, emptyMessage, renderer) {
        if (!container) {
            return;
        }

        if (!items.length) {
            container.innerHTML = `<div class="empty-state">${emptyMessage}</div>`;
            return;
        }

        container.innerHTML = items.slice(0, 4).map(renderer).join("");
    }

    function renderDashboardLists() {
        renderList(dashboardPapers, state.papers, "No uploaded papers yet.", (paper) => `
            <article class="data-item compact">
                <div>
                    <h3>${escapeHTML(paper.filename)}</h3>
                    <p>Uploaded ${formatDate(paper.upload_time)}</p>
                </div>
            </article>
        `);

        renderList(dashboardFavorites, state.favorites, "No favorite papers yet.", (favorite) => `
            <article class="data-item compact">
                <div>
                    <h3>${escapeHTML(favorite.paper_name)}</h3>
                    <p>Saved ${formatDate(favorite.saved_at)}</p>
                </div>
            </article>
        `);

        renderList(dashboardSearches, state.searches, "No search history yet.", (entry) => `
            <article class="data-item compact">
                <div>
                    <h3>${escapeHTML(entry.query)}</h3>
                    <p>${formatDate(entry.searched_at)}</p>
                </div>
            </article>
        `);

        renderList(dashboardQueryLogs, state.queryLogs, "No query logs yet.", (log) => `
            <article class="data-item compact">
                <div>
                    <h3>${escapeHTML(log.query)}</h3>
                    <p>${escapeHTML(log.response_time)} · ${formatDate(log.timestamp)}</p>
                </div>
            </article>
        `);
    }

    function setDashboardLoading(isLoading) {
        [dashboardPapers, dashboardFavorites, dashboardSearches, dashboardQueryLogs]
            .filter(Boolean)
            .forEach((container) => {
                if (isLoading) {
                    container.innerHTML = '<div class="empty-state">Loading...</div>';
                }
            });
    }

    async function loadDashboard(options = {}) {
        const renderChat = options.renderChat !== false;
        setDashboardLoading(true);

        try {
            const [profile, papers, chats, searches, queryLogs, favorites] = await Promise.all([
                apiFetch("/profile"),
                apiFetch("/my-papers"),
                apiFetch("/my-chat-history"),
                apiFetch("/search-history"),
                apiFetch("/query-logs"),
                apiFetch("/favorites")
            ]);

            state.profile = profile;
            state.papers = Array.isArray(papers) ? papers : [];
            state.chats = Array.isArray(chats) ? chats : [];
            state.searches = Array.isArray(searches) ? searches : [];
            state.queryLogs = Array.isArray(queryLogs) ? queryLogs : [];
            state.favorites = Array.isArray(favorites) ? favorites : [];

            saveUser(profile);
            updateStats();
            renderDashboardLists();

            if (renderChat && window.ResearchGPTChat) {
                window.ResearchGPTChat.renderHistory(state.chats);
            }
        } catch (error) {
            showToast(error.message, "error");
            renderDashboardLists();
        }
    }

    updateProfileSummary();

    if (window.ResearchGPTChat) {
        window.ResearchGPTChat.initChat({
            historyLimit: 5,
            onAfterSend: async () => {
                await loadDashboard({ renderChat: false });
            }
        });
    }

    if (focusChat && questionInput) {
        focusChat.addEventListener("click", () => {
            questionInput.focus();
        });
    }

    if (refreshHistory) {
        refreshHistory.addEventListener("click", () => {
            loadDashboard({ renderChat: true });
        });
    }

    if (refreshDashboardData) {
        refreshDashboardData.addEventListener("click", () => {
            loadDashboard({ renderChat: false });
        });
    }

    window.ResearchGPTDashboard = {
        refresh: loadDashboard,
        state
    };

    loadDashboard({ renderChat: true });
});
