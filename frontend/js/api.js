(function () {
    "use strict";

    const TOKEN_KEY = "researchgpt_token";
    const API_BASE_KEY = "researchgpt_api_base";
    const API_BASE = (
        window.RESEARCHGPT_API_BASE ||
        localStorage.getItem(API_BASE_KEY) ||
        "http://localhost:8000"
    ).replace(/\/+$/, "");

    const STATUS_MESSAGES = {
        0: `Could not reach the API at ${API_BASE}. Make sure the FastAPI server is running.`,
        401: "Your session has expired. Please log in again.",
        403: "You do not have permission to perform this action.",
        404: "The requested resource was not found.",
        500: "The server ran into a problem. Please try again."
    };

    let unauthorizedHandler = null;

    class ApiError extends Error {
        constructor(message, status, data) {
            super(message);
            this.name = "ApiError";
            this.status = status;
            this.data = data;
        }
    }

    function getAccessToken() {
        return localStorage.getItem(TOKEN_KEY);
    }

    function setAccessToken(token) {
        if (!token) {
            return;
        }
        localStorage.setItem(TOKEN_KEY, token);
    }

    function clearAccessToken() {
        localStorage.removeItem(TOKEN_KEY);
    }

    function setUnauthorizedHandler(handler) {
        unauthorizedHandler = typeof handler === "function" ? handler : null;
    }

    function buildApiUrl(path, params) {
        const rawUrl = path.startsWith("http")
            ? path
            : `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
        const url = new URL(rawUrl);

        if (params) {
            Object.entries(params).forEach(([key, value]) => {
                if (value !== undefined && value !== null && value !== "") {
                    url.searchParams.set(key, value);
                }
            });
        }

        return url.toString();
    }

    function extractApiMessage(data, fallback) {
        if (data && data.error) {
            const details = data.error.details;
            if (Array.isArray(details) && details.length > 0) {
                return details
                    .map((detail) => detail.msg || detail.message)
                    .filter(Boolean)
                    .join(" ") || data.error.message || fallback;
            }
            return data.error.message || fallback;
        }

        if (Array.isArray(data && data.detail)) {
            return data.detail
                .map((detail) => detail.msg || detail.message)
                .filter(Boolean)
                .join(" ") || fallback;
        }

        if (data && data.detail) {
            return data.detail;
        }

        if (data && data.message) {
            return data.message;
        }

        return fallback;
    }

    function friendlyMessage(status, data, fallback) {
        const apiMessage = extractApiMessage(data, "");

        if (status === 401) {
            return STATUS_MESSAGES[401];
        }

        if (status === 403 || status === 404 || status >= 500) {
            return apiMessage && apiMessage !== "Internal server error."
                ? apiMessage
                : STATUS_MESSAGES[status] || STATUS_MESSAGES[500];
        }

        return apiMessage || fallback || `Request failed with status ${status}.`;
    }

    async function parseResponse(response) {
        const text = await response.text();
        if (!text) {
            return null;
        }

        try {
            return JSON.parse(text);
        } catch (error) {
            return { message: text };
        }
    }

    function normalizeRequestOptions(options) {
        const requestOptions = { ...options };
        const headers = new Headers(requestOptions.headers || {});

        if (
            requestOptions.body &&
            !(requestOptions.body instanceof FormData) &&
            !(requestOptions.body instanceof Blob) &&
            typeof requestOptions.body !== "string"
        ) {
            headers.set("Content-Type", "application/json");
            requestOptions.body = JSON.stringify(requestOptions.body);
        }

        requestOptions.headers = headers;
        return requestOptions;
    }

    function handleUnauthorized(error, config) {
        if (config.skipUnauthorizedHandler) {
            return;
        }

        clearAccessToken();

        if (unauthorizedHandler) {
            unauthorizedHandler(error);
        }
    }

    async function apiFetch(path, options = {}, config = {}) {
        const requestOptions = normalizeRequestOptions(options);
        const headers = requestOptions.headers;
        const shouldAttachAuth = config.auth !== false;
        const token = config.token || getAccessToken();

        if (shouldAttachAuth) {
            if (!token) {
                const error = new ApiError("Please log in to continue.", 401, null);
                handleUnauthorized(error, config);
                throw error;
            }
            headers.set("Authorization", `Bearer ${token}`);
        }

        let response;
        try {
            response = await fetch(buildApiUrl(path, config.params), requestOptions);
        } catch (error) {
            throw new ApiError(STATUS_MESSAGES[0], 0, null);
        }

        const data = await parseResponse(response);

        if (!response.ok) {
            const message = response.status === 401 && !shouldAttachAuth
                ? extractApiMessage(data, `Request failed with status ${response.status}.`)
                : friendlyMessage(response.status, data);
            const error = new ApiError(message, response.status, data);

            if (response.status === 401 && shouldAttachAuth) {
                handleUnauthorized(error, config);
            }

            throw error;
        }

        return data;
    }

    function uploadWithProgress(path, options = {}, config = {}) {
        const file = options.file;
        const fieldName = options.fieldName || "file";
        const method = options.method || "POST";
        const extraFields = options.extraFields || {};
        const onProgress = options.onProgress;
        const shouldAttachAuth = config.auth !== false;
        const token = config.token || getAccessToken();

        return new Promise((resolve, reject) => {
            if (!file) {
                reject(new ApiError("Choose a PDF file to upload.", 400, null));
                return;
            }

            if (shouldAttachAuth && !token) {
                const error = new ApiError("Please log in to continue.", 401, null);
                handleUnauthorized(error, config);
                reject(error);
                return;
            }

            const formData = new FormData();
            formData.append(fieldName, file);

            Object.entries(extraFields).forEach(([key, value]) => {
                if (value !== undefined && value !== null) {
                    formData.append(key, value);
                }
            });

            const xhr = new XMLHttpRequest();
            xhr.open(method, buildApiUrl(path, config.params));

            if (shouldAttachAuth) {
                xhr.setRequestHeader("Authorization", `Bearer ${token}`);
            }

            xhr.upload.addEventListener("progress", (event) => {
                if (event.lengthComputable && typeof onProgress === "function") {
                    onProgress((event.loaded / event.total) * 100, event);
                }
            });

            xhr.addEventListener("load", () => {
                let data = null;
                try {
                    data = JSON.parse(xhr.responseText || "null");
                } catch (error) {
                    data = { message: xhr.responseText };
                }

                if (xhr.status >= 200 && xhr.status < 300) {
                    resolve(data);
                    return;
                }

                const error = new ApiError(
                    friendlyMessage(xhr.status, data, `Upload failed with status ${xhr.status}.`),
                    xhr.status,
                    data
                );

                if (xhr.status === 401 && shouldAttachAuth) {
                    handleUnauthorized(error, config);
                }

                reject(error);
            });

            xhr.addEventListener("error", () => {
                reject(new ApiError(STATUS_MESSAGES[0], 0, null));
            });

            xhr.send(formData);
        });
    }

    const api = {
        API_BASE,
        API_BASE_KEY,
        TOKEN_KEY,
        ApiError,
        apiFetch,
        buildApiUrl,
        clearAccessToken,
        extractApiMessage,
        getAccessToken,
        setAccessToken,
        setUnauthorizedHandler,
        uploadWithProgress
    };

    window.ResearchGPTApi = api;
    window.ResearchGPT = {
        ...(window.ResearchGPT || {}),
        ...api
    };
})();
