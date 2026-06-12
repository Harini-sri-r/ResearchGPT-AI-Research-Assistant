window.ResearchGPT.onReady(() => {
    "use strict";

    const {
        apiFetch,
        buildApiUrl,
        escapeHTML,
        extractApiMessage,
        formatDate,
        getToken,
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
                <button class="button button-ghost" type="button" data-paper-view="${paper.id}">View</button>
                <button class="button button-ghost" type="button" data-paper-download="${paper.id}" data-paper-filename="${escapeHTML(paper.filename)}">Download</button>
                <button class="button button-ghost button-danger" type="button" data-paper-delete="${paper.id}" data-paper-filename="${escapeHTML(paper.filename)}">Delete</button>
                <button class="button button-primary" type="button" data-favorite-paper="${escapeHTML(paper.filename)}">Favorite</button>
            </div>
        `;

        return item;
    }

    async function fetchPaperBlob(path) {
        const token = getToken();
        if (!token) {
            throw new Error("Please log in to continue.");
        }

        let response;
        try {
            response = await fetch(
                buildApiUrl(path),
                {
                    headers: {
                        Authorization: `Bearer ${token}`
                    }
                }
            );
        } catch (error) {
            throw new Error("Could not reach the API. Make sure the FastAPI server is running.");
        }

        if (!response.ok) {
            const text = await response.text();
            let data = null;

            try {
                data = text ? JSON.parse(text) : null;
            } catch (error) {
                data = { message: text };
            }

            throw new Error(
                extractApiMessage(
                    data,
                    `Paper request failed with status ${response.status}.`
                )
            );
        }

        return response.blob();
    }

    async function viewPaper(paperId) {
        const openedWindow = window.open("about:blank", "_blank");
        if (openedWindow) {
            openedWindow.opener = null;
            openedWindow.document.title = "Opening paper...";
            openedWindow.document.body.innerHTML = "<p style=\"font-family: system-ui, sans-serif; padding: 1rem;\">Opening paper...</p>";
        }

        let blob;

        try {
            blob = await fetchPaperBlob(`/papers/${encodeURIComponent(paperId)}/view`);
        } catch (error) {
            if (openedWindow) {
                openedWindow.close();
            }
            throw error;
        }

        const url = URL.createObjectURL(blob);

        if (!openedWindow) {
            window.location.href = url;
        } else {
            openedWindow.location.href = url;
        }

        window.setTimeout(() => {
            URL.revokeObjectURL(url);
        }, 60000);
    }

    async function downloadPaper(paperId, filename) {
        const blob = await fetchPaperBlob(`/papers/${encodeURIComponent(paperId)}/download`);
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");

        link.href = url;
        link.download = filename || "paper.pdf";
        document.body.appendChild(link);
        link.click();
        link.remove();

        window.setTimeout(() => {
            URL.revokeObjectURL(url);
        }, 60000);
    }

    async function deletePaper(paperId, filename) {
        const confirmed = window.confirm(
            `Delete "${filename || "this paper"}"? This removes it from your library and search index.`
        );

        if (!confirmed) {
            return;
        }

        const response = await apiFetch(
            `/papers/${encodeURIComponent(paperId)}`,
            {
                method: "DELETE"
            }
        );

        showToast(
            response && response.message ? response.message : "Paper deleted.",
            "success"
        );
        await loadPapers();
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
            const button = event.target.closest("button");
            if (!button) {
                return;
            }

            const viewId = button.dataset.paperView;
            const downloadId = button.dataset.paperDownload;
            const deleteId = button.dataset.paperDelete;
            const favoritePaper = button.dataset.favoritePaper;

            if (!viewId && !downloadId && !deleteId && !favoritePaper) {
                return;
            }

            button.disabled = true;

            try {
                if (viewId) {
                    await viewPaper(viewId);
                } else if (downloadId) {
                    await downloadPaper(downloadId, button.dataset.paperFilename);
                } else if (deleteId) {
                    await deletePaper(deleteId, button.dataset.paperFilename);
                } else if (window.ResearchGPTFavorites) {
                    await window.ResearchGPTFavorites.addFavorite(favoritePaper);
                } else {
                    await apiFetch("/favorites", {
                        method: "POST",
                        body: { paper_name: favoritePaper }
                    });
                    showToast("Favorite added.", "success");
                }
            } catch (error) {
                showToast(
                    error.message,
                    error.status === 409 ? "warning" : "error"
                );
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
