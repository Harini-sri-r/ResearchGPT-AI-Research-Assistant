window.ResearchGPT.onReady(() => {
    "use strict";

    const {
        apiFetch,
        escapeHTML,
        formatDate,
        isLoggedIn,
        showInlineMessage,
        showToast,
        uploadWithProgress
    } = window.ResearchGPT;

    if (!isLoggedIn()) {
        return;
    }

    const dropZone = document.getElementById("dropZone");
    const fileInput = document.getElementById("fileInput");
    const chooseFile = document.getElementById("chooseFile");
    const progress = document.getElementById("uploadProgress");
    const status = document.getElementById("uploadStatus");
    const uploadedList = document.getElementById("uploadedList");
    const refreshPapers = document.getElementById("refreshPapers");

    let isUploading = false;

    function setProgress(value) {
        if (progress) {
            progress.style.width = `${Math.max(0, Math.min(100, value))}%`;
        }
    }

    function setUploading(value) {
        isUploading = value;
        if (chooseFile) {
            chooseFile.disabled = value;
        }
        if (refreshPapers) {
            refreshPapers.disabled = value;
        }
        if (dropZone) {
            dropZone.classList.toggle("is-uploading", value);
        }
    }

    function paperRow(paper) {
        const item = document.createElement("article");
        item.className = "data-item";

        item.innerHTML = `
            <div>
                <h3>${escapeHTML(paper.filename)}</h3>
                <p>Uploaded ${formatDate(paper.upload_time)}</p>
            </div>
            <div class="item-actions">
                <button class="button button-ghost" type="button" disabled title="This backend exposes paper metadata only.">View</button>
                <button class="button button-ghost" type="button" disabled title="This backend exposes paper metadata only.">Download</button>
                <button class="button button-ghost" type="button" disabled title="No delete paper API is available.">Delete</button>
                <button class="button button-primary" type="button" data-favorite-paper="${escapeHTML(paper.filename)}">Favorite</button>
            </div>
        `;

        return item;
    }

    function renderPapers(papers) {
        if (!uploadedList) {
            return;
        }

        uploadedList.innerHTML = "";

        if (!papers.length) {
            uploadedList.innerHTML = '<div class="empty-state">No uploaded papers yet.</div>';
            return;
        }

        papers.forEach((paper) => {
            uploadedList.appendChild(paperRow(paper));
        });
    }

    async function loadPapers() {
        if (!uploadedList) {
            return;
        }

        try {
            uploadedList.innerHTML = '<div class="empty-state">Loading papers...</div>';
            const papers = await apiFetch("/my-papers");
            renderPapers(Array.isArray(papers) ? papers : []);
        } catch (error) {
            uploadedList.innerHTML = '<div class="empty-state">Unable to load papers.</div>';
            showToast(error.message, "error");
        }
    }

    async function uploadFile(file) {
        if (!file || isUploading) {
            return;
        }

        if (!file.name.toLowerCase().endsWith(".pdf")) {
            showInlineMessage(status, "Please choose a PDF file.", "error");
            showToast("Please choose a PDF file.", "error");
            return;
        }

        setUploading(true);
        setProgress(0);
        showInlineMessage(status, `Uploading ${file.name}...`);

        try {
            const data = await uploadWithProgress("/upload", {
                file,
                onProgress: setProgress
            });

            setProgress(100);
            showInlineMessage(status, data && data.message ? data.message : "Upload complete.", "success");
            showToast(data && data.message ? data.message : "Upload complete.", "success");
            await loadPapers();
        } catch (error) {
            setProgress(0);
            showInlineMessage(status, error.message, "error");
            showToast(error.message, "error");
        } finally {
            setUploading(false);
            if (fileInput) {
                fileInput.value = "";
            }
        }
    }

    if (chooseFile && fileInput) {
        chooseFile.addEventListener("click", () => fileInput.click());
        fileInput.addEventListener("change", () => uploadFile(fileInput.files[0]));
    }

    if (dropZone) {
        ["dragenter", "dragover"].forEach((eventName) => {
            dropZone.addEventListener(eventName, (event) => {
                event.preventDefault();
                if (!isUploading) {
                    dropZone.classList.add("drag-over");
                }
            });
        });

        ["dragleave", "drop"].forEach((eventName) => {
            dropZone.addEventListener(eventName, (event) => {
                event.preventDefault();
                dropZone.classList.remove("drag-over");
            });
        });

        dropZone.addEventListener("drop", (event) => {
            uploadFile(event.dataTransfer.files[0]);
        });
    }

    if (uploadedList) {
        uploadedList.addEventListener("click", async (event) => {
            const button = event.target.closest("[data-favorite-paper]");
            if (!button) {
                return;
            }

            button.disabled = true;

            try {
                if (window.ResearchGPTFavorites) {
                    await window.ResearchGPTFavorites.addFavorite(button.dataset.favoritePaper);
                } else {
                    await apiFetch("/favorites", {
                        method: "POST",
                        body: { paper_name: button.dataset.favoritePaper }
                    });
                    showToast("Favorite added.", "success");
                }
            } catch (error) {
                showToast(error.message, error.status === 409 ? "warning" : "error");
            } finally {
                button.disabled = false;
            }
        });
    }

    if (refreshPapers) {
        refreshPapers.addEventListener("click", loadPapers);
    }

    window.ResearchGPTPapers = {
        refresh: loadPapers
    };

    loadPapers();
});
