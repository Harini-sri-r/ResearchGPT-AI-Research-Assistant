window.ResearchGPT.onReady(() => {
    "use strict";

    const {
        apiFetch,
        formatDate,
        getUser,
        isLoggedIn,
        saveUser,
        showToast
    } = window.ResearchGPT;

    if (!isLoggedIn()) {
        return;
    }

    const profileAvatar = document.getElementById("profileAvatar");
    const profileUsername = document.getElementById("profileUsername");
    const profileEmail = document.getElementById("profileEmail");
    const detailUsername = document.getElementById("detailUsername");
    const detailEmail = document.getElementById("detailEmail");
    const detailCreated = document.getElementById("detailCreated");

    function renderProfile(user) {
        if (!user) {
            return;
        }

        const initial = user.username ? user.username.charAt(0).toUpperCase() : "R";
        profileAvatar.textContent = initial;
        profileUsername.textContent = user.username || "Researcher";
        profileEmail.textContent = user.email || "-";
        detailUsername.textContent = user.username || "-";
        detailEmail.textContent = user.email || "-";
        detailCreated.textContent = formatDate(user.created_at);
    }

    async function loadProfile() {
        renderProfile(getUser());

        try {
            const profile = await apiFetch("/profile");
            saveUser(profile);
            renderProfile(profile);
        } catch (error) {
            showToast(error.message, "error");
        }
    }

    loadProfile();
});
