(function () {
    "use strict";

    let pageController = null;

    function app() {
        return window.ResearchGPT;
    }

    async function fetchFavorites() {
        return app().apiFetch("/favorites");
    }

    function renderFavorites(favorites) {
        if (!pageController || !pageController.list) {
            return;
        }

        const { escapeHTML, formatDate } = app();

        if (!favorites.length) {
            pageController.list.innerHTML = '<div class="empty-state">No favorite papers yet.</div>';
            return;
        }

        pageController.list.innerHTML = favorites.map((favorite) => `
            <article class="data-item">
                <div>
                    <h3>${escapeHTML(favorite.paper_name)}</h3>
                    <p>Saved ${formatDate(favorite.saved_at)}</p>
                </div>
                <div class="item-actions">
                    <button class="button button-ghost" type="button" data-remove-favorite="${favorite.id}">Remove Favorite</button>
                </div>
            </article>
        `).join("");
    }

    async function refreshFavorites() {
        if (!pageController || !pageController.list) {
            return [];
        }

        try {
            pageController.list.innerHTML = '<div class="empty-state">Loading favorites...</div>';
            const favorites = await fetchFavorites();
            const normalizedFavorites = Array.isArray(favorites) ? favorites : [];
            renderFavorites(normalizedFavorites);
            return normalizedFavorites;
        } catch (error) {
            pageController.list.innerHTML = '<div class="empty-state">Unable to load favorites.</div>';
            app().showToast(error.message, "error");
            return [];
        }
    }

    async function addFavorite(paperName) {
        const normalizedName = String(paperName || "").trim();
        if (!normalizedName) {
            throw new Error("Choose a paper to favorite.");
        }

        const favorite = await app().apiFetch("/favorites", {
            method: "POST",
            body: { paper_name: normalizedName }
        });

        app().showToast("Favorite added.", "success");
        window.dispatchEvent(new CustomEvent("researchgpt:favorites-changed"));

        if (pageController) {
            await refreshFavorites();
        }

        return favorite;
    }

    async function removeFavorite(id) {
        const response = await app().apiFetch(`/favorites/${encodeURIComponent(id)}`, {
            method: "DELETE"
        });

        app().showToast(response && response.message ? response.message : "Favorite removed.", "success");
        window.dispatchEvent(new CustomEvent("researchgpt:favorites-changed"));

        if (pageController) {
            await refreshFavorites();
        }

        return response;
    }

    function initFavoritesPage() {
        const list = document.getElementById("favoritesList");
        const refreshButton = document.getElementById("refreshFavorites");
        const form = document.getElementById("favoriteForm");
        const input = document.getElementById("favoritePaperName");

        if (!list) {
            return;
        }

        pageController = { form, input, list, refreshButton };

        list.addEventListener("click", async (event) => {
            const button = event.target.closest("[data-remove-favorite]");
            if (!button) {
                return;
            }

            button.disabled = true;

            try {
                await removeFavorite(button.dataset.removeFavorite);
            } catch (error) {
                app().showToast(error.message, "error");
                button.disabled = false;
            }
        });

        if (refreshButton) {
            refreshButton.addEventListener("click", refreshFavorites);
        }

        if (form && input) {
            form.addEventListener("submit", async (event) => {
                event.preventDefault();
                const button = form.querySelector('button[type="submit"]');
                app().setButtonLoading(button, true);

                try {
                    await addFavorite(input.value);
                    input.value = "";
                } catch (error) {
                    app().showToast(error.message, error.status === 409 ? "warning" : "error");
                } finally {
                    app().setButtonLoading(button, false);
                    input.focus();
                }
            });
        }

        refreshFavorites();
    }

    window.ResearchGPTFavorites = {
        addFavorite,
        fetchFavorites,
        refreshFavorites,
        removeFavorite
    };

    window.ResearchGPT.onReady(() => {
        if (!window.ResearchGPT.isLoggedIn()) {
            return;
        }
        initFavoritesPage();
    });
})();
