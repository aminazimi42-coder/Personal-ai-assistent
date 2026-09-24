const resultBox = document.getElementById("resultBox");
const statusText = document.getElementById("statusText");
const tasksList = document.getElementById("tasksList");
const appointmentsList = document.getElementById("appointmentsList");
const remindersList = document.getElementById("remindersList");
const messageInput = document.getElementById("messageInput");
const dueDateInput = document.getElementById("dueDateInput");
const sendButton = document.getElementById("sendButton");
const refreshTasksButton = document.getElementById("refreshTasksButton");
const refreshRemindersButton = document.getElementById("refreshRemindersButton");

const emailInput = document.getElementById("emailInput");
const passwordInput = document.getElementById("passwordInput");
const signupButton = document.getElementById("signupButton");
const loginButton = document.getElementById("loginButton");
const logoutButton = document.getElementById("logoutButton");
const authStatusText = document.getElementById("authStatusText");
const nameInput = document.getElementById("nameInput");

const togglePasswordButton = document.getElementById("togglePasswordButton");

const refreshLocationButton = document.getElementById("refreshLocationButton");
const locationStatusText = document.getElementById("locationStatusText");
const locationLiveText = document.getElementById("locationLiveText");
const locationCountryText = document.getElementById("locationCountryText");
const locationCityText = document.getElementById("locationCityText");
const locationLatitudeText = document.getElementById("locationLatitudeText");
const locationLongitudeText = document.getElementById("locationLongitudeText");

const startVoiceButton = document.getElementById("startVoiceButton");
const stopVoiceButton = document.getElementById("stopVoiceButton");
const voiceStatusText = document.getElementById("voiceStatusText");
const voiceTranscriptBox = document.getElementById("voiceTranscriptBox");

const refreshExchangeRatesButton = document.getElementById("refreshExchangeRatesButton");
const exchangeRatesStatusText = document.getElementById("exchangeRatesStatusText");
const exchangeRatesBaseText = document.getElementById("exchangeRatesBaseText");
const exchangeRateEurText = document.getElementById("exchangeRateEurText");
const exchangeRateGbpText = document.getElementById("exchangeRateGbpText");
const exchangeRateCadText = document.getElementById("exchangeRateCadText");
const exchangeRateTryText = document.getElementById("exchangeRateTryText");
const exchangeRateAedText = document.getElementById("exchangeRateAedText");
const exchangeRatesUpdatedText = document.getElementById("exchangeRatesUpdatedText");

const customCurrencyInput = document.getElementById("customCurrencyInput");
const findCurrencyButton = document.getElementById("findCurrencyButton");
const customCurrencyResultText = document.getElementById("customCurrencyResultText");

const refreshWeatherButton = document.getElementById("refreshWeatherButton");
const weatherStatusText = document.getElementById("weatherStatusText");
const weatherCityText = document.getElementById("weatherCityText");
const weatherTempText = document.getElementById("weatherTempText");
const weatherConditionText = document.getElementById("weatherConditionText");
const weatherHumidityText = document.getElementById("weatherHumidityText");
const weatherWindText = document.getElementById("weatherWindText");

/* ---- Quota panel elements ---- */
const loginPanel = document.getElementById("loginPanel");
const accountQuotaPanel = document.getElementById("accountQuotaPanel");
const refreshQuotaButton = document.getElementById("refreshQuotaButton");
const quotaPlanText = document.getElementById("quotaPlanText");
const quotaLimitText = document.getElementById("quotaLimitText");
const quotaUsedText = document.getElementById("quotaUsedText");
const quotaRemainingText = document.getElementById("quotaRemainingText");
const quotaStatusText = document.getElementById("quotaStatusText");

/* ---- Message error element ---- */
const messageError = document.getElementById("messageError");

const AUTH_TOKEN_STORAGE_KEY = "personal_ai_auth_token";
const LOCATION_STORAGE_KEY = "personal_ai_live_location_cache";
const AUTO_REMINDER_INTERVAL_MS = 30000;
const REMINDER_LOOKAHEAD_MS = 5 * 60 * 1000;
const REMINDER_OVERDUE_GRACE_MS = 30 * 60 * 1000;
const NOTIFICATION_COOLDOWN_MS = 60000;

let reminderAutoRefreshIntervalId = null;
let isLoadingReminders = false;
let lastReminderSignature = "";
let shownReminderIds = new Set();
let reminderAudioContext = null;
let reminderSoundEnabled = false;
let reminderSoundUnlockListenersInstalled = false;
let lastNotificationTimeMap = {};

let mediaRecorder = null;
let mediaStream = null;
let recordedAudioChunks = [];
let isVoiceRecording = false;
let voiceRecordingSupported = false;
let lastRecordedAudioBlob = null;
let lastRecordedAudioUrl = "";
let lastRecordedAudioMimeType = "";

/* Track the tab the user was on when a 401 occurred so we can return there. */
let pendingReturnTab = null;

function formatDateForDisplay(value) {
    if (!value) {
        return "No due date";
    }

    try {
        return new Date(value).toLocaleString();
    } catch (error) {
        return value;
    }
}

function formatAppointmentTimeForDisplay(value) {
    if (!value) {
        return "No time";
    }

    try {
        return new Date(value).toLocaleString();
    } catch (error) {
        return value;
    }
}

function escapeHtml(value) {
    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function getAuthToken() {
    try {
        return localStorage.getItem(AUTH_TOKEN_STORAGE_KEY) || "";
    } catch (error) {
        return "";
    }
}

function setAuthToken(token) {
    try {
        if (token) {
            localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, token);
        }
    } catch (error) {
        console.error("Failed to save auth token:", error);
    }
}

function clearAuthToken() {
    try {
        localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
    } catch (error) {
        console.error("Failed to clear auth token:", error);
    }
}

function getAuthHeaders(extraHeaders = {}) {
    const token = getAuthToken();
    const headers = { ...extraHeaders };

    if (token) {
        headers["Authorization"] = `Bearer ${token}`;
    }

    return headers;
}

function updateAuthStatus(text) {
    if (authStatusText) {
        authStatusText.textContent = text;
    }
}

function updateLoggedInUiState() {
    const hasToken = !!getAuthToken();
    if (loginPanel) {
        loginPanel.classList.toggle("is-hidden", hasToken);
    }
    if (accountQuotaPanel) {
        accountQuotaPanel.classList.toggle("is-hidden", !hasToken);
    }
    updateAuthStatus(hasToken ? "Logged in" : "Not logged in");
    updateSendButtonState();
}

/* ---- Send button is disabled until auth is valid ---- */
function updateSendButtonState() {
    if (!sendButton) return;
    const hasToken = !!getAuthToken();
    sendButton.disabled = !hasToken;
    if (!hasToken && messageError) {
        messageError.textContent = "Please log in on the Account tab to send messages.";
    } else if (messageError) {
        messageError.textContent = "";
    }
}

function togglePasswordVisibility() {
    if (!passwordInput || !togglePasswordButton) {
        return;
    }

    const isPasswordHidden = passwordInput.type === "password";

    passwordInput.type = isPasswordHidden ? "text" : "password";
    togglePasswordButton.textContent = isPasswordHidden ? "🙈" : "👁";
    togglePasswordButton.setAttribute(
        "aria-label",
        isPasswordHidden ? "Hide password" : "Show password"
    );
    togglePasswordButton.setAttribute(
        "title",
        isPasswordHidden ? "Hide password" : "Show password"
    );
}

/* ---- On 401: show a real login panel that returns to the same tab ---- */
function showLoginPanelForAuth() {
    const activeTab = document.querySelector(".bottom-nav-item.active");
    pendingReturnTab = activeTab ? activeTab.dataset.tab : null;

    updateAuthStatus("Session expired — please log in again.");

    if (typeof showAppTab === "function") {
        showAppTab("account");
    }

    if (loginPanel) {
        loginPanel.classList.remove("is-hidden");
    }
    if (accountQuotaPanel) {
        accountQuotaPanel.classList.add("is-hidden");
    }

    updateSendButtonState();
}

async function authorizedFetch(url, options = {}) {
    const existingHeaders = options.headers || {};
    const finalOptions = {
        ...options,
        headers: getAuthHeaders(existingHeaders)
    };

    const response = await fetch(url, finalOptions);

    if (response.status === 401) {
        clearAuthToken();
        stopReminderAutoRefresh();
        shownReminderIds = new Set();
        showLoginPanelForAuth();

        if (statusText) {
            statusText.textContent = "Please log in on the Account tab.";
        }
    }

    return response;
}

function renderTasks(tasks) {
    if (!tasksList) {
        return;
    }

    if (!tasks || !Array.isArray(tasks) || tasks.length === 0) {
        tasksList.innerHTML = `<div class="loading">No tasks yet.</div>`;
        return;
    }

    tasksList.innerHTML = tasks.map(task => {
        const isDone = task.status === "done";
        const title = task.title || "Untitled task";
        const description = task.description || "No description";
        const priority = task.priority || "medium";
        const status = task.status || "pending";
        const dueDate = formatDateForDisplay(task.due_date);

        return `
        <div class="task-item ${isDone ? "task-done" : ""}">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;">
                <div>
                    <strong style="font-size:15px;color:var(--text-primary);">${escapeHtml(title)}</strong><br>
                    <span style="color:var(--text-muted);font-size:13px;">
                        ${escapeHtml(description)}
                    </span>
                </div>

                <span class="badge badge-status">
                    ${escapeHtml(status)}
                </span>
            </div>

            <div style="margin-top:10px;font-size:13px;color:var(--text-muted);">
                Due: ${escapeHtml(dueDate)} · Priority: ${escapeHtml(priority)}
            </div>

            <div class="task-actions" style="margin-top:12px;">
                <button class="done-btn" onclick="updateTask(${task.id}, 'done')">✔ Done</button>
                <button class="pending-btn" onclick="updateTask(${task.id}, 'pending')">↩ Pending</button>
                <button class="delete-btn" onclick="deleteTask(${task.id})">🗑 Delete</button>
            </div>
        </div>
        `;
    }).join("");
}

function renderAppointments(appointments) {
    if (!appointmentsList) {
        return;
    }

    if (!appointments || !Array.isArray(appointments) || appointments.length === 0) {
        appointmentsList.innerHTML = `<div class="loading">No appointments yet.</div>`;
        return;
    }

    appointmentsList.innerHTML = appointments.map(appointment => {
        return `
        <div class="task-item">
            <strong>${escapeHtml(appointment.title)}</strong><br>
            ${escapeHtml(appointment.description || "No description")}<br>
            <span style="color:var(--text-muted);font-size:13px;">
                Time: ${escapeHtml(formatAppointmentTimeForDisplay(appointment.appointment_time))}
            </span><br>
            <span style="color:var(--text-muted);font-size:13px;">
                Location: ${escapeHtml(appointment.location || "No location")}
            </span><br>
            <span class="badge badge-status" style="margin-top:6px;">Status: ${escapeHtml(appointment.status || "scheduled")}</span>
        </div>
        `;
    }).join("");
}

function supportsBrowserNotifications() {
    return typeof window !== "undefined" && "Notification" in window;
}

async function ensureBrowserNotificationPermission() {
    if (!supportsBrowserNotifications()) {
        return "unsupported";
    }

    if (Notification.permission === "granted") {
        return "granted";
    }

    if (Notification.permission === "denied") {
        return "denied";
    }

    try {
        return await Notification.requestPermission();
    } catch (error) {
        console.error("Failed to request notification permission:", error);
        return "error";
    }
}

function showBrowserNotification(message) {
    if (!supportsBrowserNotifications()) {
        return;
    }

    if (Notification.permission !== "granted") {
        return;
    }

    try {
        const notification = new Notification("Reminder", {
            body: message,
            tag: `reminder-${message}`,
            renotify: true
        });

        window.setTimeout(() => {
            try {
                notification.close();
            } catch (error) {
                console.error("Failed to close browser notification:", error);
            }
        }, 5000);
    } catch (error) {
        console.error("Failed to show browser notification:", error);
    }
}

async function unlockReminderSound() {
    try {
        if (!reminderAudioContext) {
            reminderAudioContext = new (window.AudioContext || window.webkitAudioContext)();
        }

        if (reminderAudioContext.state === "suspended") {
            await reminderAudioContext.resume();
        }

        const oscillator = reminderAudioContext.createOscillator();
        const gainNode = reminderAudioContext.createGain();

        oscillator.type = "sine";
        oscillator.frequency.setValueAtTime(440, reminderAudioContext.currentTime);
        gainNode.gain.setValueAtTime(0.0001, reminderAudioContext.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.001, reminderAudioContext.currentTime + 0.01);
        gainNode.gain.exponentialRampToValueAtTime(0.0001, reminderAudioContext.currentTime + 0.03);

        oscillator.connect(gainNode);
        gainNode.connect(reminderAudioContext.destination);

        oscillator.start(reminderAudioContext.currentTime);
        oscillator.stop(reminderAudioContext.currentTime + 0.03);

        reminderSoundEnabled = true;
    } catch (error) {
        console.error("Failed to unlock reminder sound:", error);
    }
}

function installReminderSoundUnlockListeners() {
    if (reminderSoundUnlockListenersInstalled) {
        return;
    }

    const unlockOnce = async function () {
        await unlockReminderSound();

        if (reminderSoundEnabled) {
            document.removeEventListener("touchstart", unlockOnce);
            document.removeEventListener("touchend", unlockOnce);
            document.removeEventListener("click", unlockOnce);
            document.removeEventListener("keydown", unlockOnce);
        }
    };

    document.addEventListener("touchstart", unlockOnce, { passive: true });
    document.addEventListener("touchend", unlockOnce, { passive: true });
    document.addEventListener("click", unlockOnce);
    document.addEventListener("keydown", unlockOnce);

    reminderSoundUnlockListenersInstalled = true;
}

async function playReminderSound() {
    if (!reminderSoundEnabled) {
        return;
    }

    try {
        if (!reminderAudioContext) {
            reminderAudioContext = new (window.AudioContext || window.webkitAudioContext)();
        }

        if (reminderAudioContext.state === "suspended") {
            await reminderAudioContext.resume();
        }

        const oscillator = reminderAudioContext.createOscillator();
        const gainNode = reminderAudioContext.createGain();

        oscillator.type = "sine";
        oscillator.frequency.setValueAtTime(880, reminderAudioContext.currentTime);
        gainNode.gain.setValueAtTime(0.001, reminderAudioContext.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.12, reminderAudioContext.currentTime + 0.02);
        gainNode.gain.exponentialRampToValueAtTime(0.001, reminderAudioContext.currentTime + 0.28);

        oscillator.connect(gainNode);
        gainNode.connect(reminderAudioContext.destination);

        oscillator.start(reminderAudioContext.currentTime);
        oscillator.stop(reminderAudioContext.currentTime + 0.28);
    } catch (error) {
        console.error("Failed to play reminder sound:", error);
    }
}

async function showNotification(message, key = "") {
    const now = Date.now();

    if (key) {
        const lastTime = lastNotificationTimeMap[key] || 0;
        if (now - lastTime < NOTIFICATION_COOLDOWN_MS) {
            return;
        }
        lastNotificationTimeMap[key] = now;
    }

    await playReminderSound();
    showBrowserNotification(message);

    const existingToast = document.getElementById("reminderToast");
    if (existingToast) {
        existingToast.remove();
    }

    const toast = document.createElement("div");
    toast.id = "reminderToast";
    toast.className = "reminder-toast";
    toast.innerHTML = `
        <div class="reminder-toast-content">
            <div class="reminder-toast-icon">⏰</div>
            <div class="reminder-toast-message">${escapeHtml(message)}</div>
            <button type="button" class="reminder-toast-close" id="reminderToastCloseButton">×</button>
        </div>
    `;

    document.body.appendChild(toast);

    const closeButton = document.getElementById("reminderToastCloseButton");
    if (closeButton) {
        closeButton.addEventListener("click", function () {
            toast.remove();
        });
    }

    window.setTimeout(() => {
        if (toast.parentNode) {
            toast.remove();
        }
    }, 5000);
}

function parseReminderDate(value) {
    if (!value) {
        return null;
    }

    const parsedDate = new Date(value);

    if (Number.isNaN(parsedDate.getTime())) {
        return null;
    }

    return parsedDate;
}

function isReminderTriggerable(dateValue) {
    const dueDate = parseReminderDate(dateValue);

    if (!dueDate) {
        return false;
    }

    const now = Date.now();
    const dueTime = dueDate.getTime();
    const differenceMs = dueTime - now;

    return differenceMs <= REMINDER_LOOKAHEAD_MS && differenceMs >= -REMINDER_OVERDUE_GRACE_MS;
}

function getReminderNotificationMessage(item, typeLabel) {
    const title = item && item.title ? String(item.title) : "Untitled";
    return `${typeLabel}: ${title}`;
}

function renderReminders(tasks, appointments) {
    if (!remindersList) {
        return;
    }

    const reminderItems = [];

    if (Array.isArray(tasks)) {
        tasks.forEach(task => {
            const reminderKey = `task-${task.id}-${task.due_date || "no-date"}`;
            let reminderClassName = "task-item";
            const shouldTriggerReminder =
                task &&
                task.status !== "done" &&
                isReminderTriggerable(task.due_date);

            if (shouldTriggerReminder && !shownReminderIds.has(reminderKey)) {
                showNotification(
                    getReminderNotificationMessage(task, "Task reminder"),
                    reminderKey
                );
                shownReminderIds.add(reminderKey);
                reminderClassName = "task-item reminder-highlight";
            }

            reminderItems.push(`
                <div class="${reminderClassName}">
                    <strong>Task reminder</strong><br>
                    Title: ${escapeHtml(task.title)}<br>
                    Due date: ${escapeHtml(formatDateForDisplay(task.due_date))}<br>
                    <span class="badge badge-status">Status: ${escapeHtml(task.status || "pending")}</span>
                </div>
            `);
        });
    }

    if (Array.isArray(appointments)) {
        appointments.forEach(appointment => {
            const reminderKey = `appointment-${appointment.id}-${appointment.appointment_time || "no-time"}`;
            let reminderClassName = "task-item";
            const shouldTriggerReminder =
                appointment &&
                (appointment.status || "scheduled") !== "done" &&
                isReminderTriggerable(appointment.appointment_time);

            if (shouldTriggerReminder && !shownReminderIds.has(reminderKey)) {
                showNotification(
                    getReminderNotificationMessage(appointment, "Appointment reminder"),
                    reminderKey
                );
                shownReminderIds.add(reminderKey);
                reminderClassName = "task-item reminder-highlight";
            }

            reminderItems.push(`
                <div class="${reminderClassName}">
                    <strong>Appointment reminder</strong><br>
                    Title: ${escapeHtml(appointment.title)}<br>
                    Time: ${escapeHtml(formatAppointmentTimeForDisplay(appointment.appointment_time))}<br>
                    <span class="badge badge-status">Status: ${escapeHtml(appointment.status || "scheduled")}</span>
                </div>
            `);
        });
    }

    if (reminderItems.length === 0) {
        remindersList.innerHTML = `<div class="loading">No reminders right now.</div>`;
        return;
    }

    remindersList.innerHTML = reminderItems.join("");
}

function buildReminderSignature(tasks, appointments) {
    return JSON.stringify({
        tasks: Array.isArray(tasks) ? tasks : [],
        appointments: Array.isArray(appointments) ? appointments : []
    });
}

function ensureReminderUiStyle() {
    /* Styles are now in the main stylesheet; no need to inject. */
}

function updateLocationStatus(text) {
    if (locationStatusText) {
        locationStatusText.textContent = text;
    }
}

function updateLocationFields(locationData) {
    if (locationLiveText) {
        locationLiveText.textContent = locationData.live || "Unknown";
    }

    if (locationCountryText) {
        locationCountryText.textContent = locationData.country || "Unknown";
    }

    if (locationCityText) {
        locationCityText.textContent = locationData.city || "Unknown";
    }

    if (locationLatitudeText) {
        locationLatitudeText.textContent =
            typeof locationData.latitude === "number"
                ? locationData.latitude.toFixed(6)
                : (locationData.latitude || "—");
    }

    if (locationLongitudeText) {
        locationLongitudeText.textContent =
            typeof locationData.longitude === "number"
                ? locationData.longitude.toFixed(6)
                : (locationData.longitude || "—");
    }
}

function saveLocationCache(locationData) {
    try {
        localStorage.setItem(LOCATION_STORAGE_KEY, JSON.stringify(locationData));
    } catch (error) {
        console.error("Failed to save location cache:", error);
    }
}

function loadLocationCache() {
    try {
        const raw = localStorage.getItem(LOCATION_STORAGE_KEY);
        if (!raw) {
            return null;
        }

        return JSON.parse(raw);
    } catch (error) {
        console.error("Failed to load location cache:", error);
        return null;
    }
}

function restoreCachedLocation() {
    const cachedLocation = loadLocationCache();
    if (!cachedLocation) {
        return;
    }

    updateLocationFields(cachedLocation);
    updateLocationStatus(cachedLocation.status || "Showing last known location.");
}

async function fetchWithTimeout(url, options = {}, timeoutMs = 10000) {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
    try {
        const response = await fetch(url, {
            ...options,
            signal: controller.signal
        });
        return response;
    } finally {
        window.clearTimeout(timeoutId);
    }
}

async function reverseGeocode(latitude, longitude) {
    const url = `https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${encodeURIComponent(latitude)}&lon=${encodeURIComponent(longitude)}`;

    const response = await fetchWithTimeout(url, {
        headers: {
            "Accept": "application/json"
        }
    }, 10000);

    if (!response.ok) {
        throw new Error("Failed to reverse geocode location");
    }

    const data = await response.json();
    const address = data.address || {};

    const country = address.country || "Unknown";

    const city =
        address.city ||
        address.town ||
        address.village ||
        address.state ||
        address.region ||
        "Unknown";

    return {
        country,
        city,
        live: city !== "Unknown" && country !== "Unknown" ? `${city}, ${country}` : country
    };
}

async function loadLiveLocation() {
    if (!navigator.geolocation) {
        updateLocationStatus("Geolocation is not supported on this device.");
        return;
    }

    updateLocationStatus("Getting live location...");

    navigator.geolocation.getCurrentPosition(
        async function (position) {
            try {
                const latitude = position.coords.latitude;
                const longitude = position.coords.longitude;

                updateLocationStatus("Resolving location details...");
                const resolved = await reverseGeocode(latitude, longitude);
                const locationData = {
                    status: "Live location loaded.",
                    live: resolved.live,
                    country: resolved.country,
                    city: resolved.city,
                    latitude,
                    longitude
                };

                updateLocationFields(locationData);
                updateLocationStatus(locationData.status);
                saveLocationCache(locationData);
            } catch (error) {
                console.error("Failed to resolve live location:", error);

                const fallbackLocation = {
                    status: "Coordinates loaded, but place name could not be resolved.",
                    live: "Live coordinates",
                    country: "Unknown",
                    city: "Unknown",
                    latitude: position.coords.latitude,
                    longitude: position.coords.longitude
                };

                updateLocationFields(fallbackLocation);
                updateLocationStatus(fallbackLocation.status);
                saveLocationCache(fallbackLocation);
            }
        },
        function (error) {
            console.error("Failed to get live location:", error);

            if (error.code === 1) {
                updateLocationStatus("Location permission was denied.");
            } else if (error.code === 2) {
                updateLocationStatus("Location is unavailable right now.");
            } else if (error.code === 3) {
                updateLocationStatus("Location request timed out.");
            } else {
                updateLocationStatus("Could not get live location.");
            }
        },
        {
            enableHighAccuracy: true,
            timeout: 15000,
            maximumAge: 0
        }
    );
}

async function loadWeather() {
    if (!weatherStatusText) {
        return;
    }

    weatherStatusText.textContent = "Loading weather...";

    try {
        const cachedLocation = loadLocationCache();

        if (!cachedLocation || !cachedLocation.latitude || !cachedLocation.longitude) {
            weatherStatusText.textContent = "Please load location first.";
            return;
        }

        const latitude = cachedLocation.latitude;
        const longitude = cachedLocation.longitude;

        const url = `https://api.open-meteo.com/v1/forecast?latitude=${encodeURIComponent(latitude)}&longitude=${encodeURIComponent(longitude)}&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m`;

        const response = await fetchWithTimeout(url, {}, 10000);

        if (!response.ok) {
            throw new Error("Failed to load weather");
        }

        const data = await response.json();
        const current = data.current || {};

        if (weatherCityText) {
            weatherCityText.textContent = cachedLocation.live || cachedLocation.city || "Current location";
        }

        if (weatherTempText) {
            weatherTempText.textContent =
                typeof current.temperature_2m === "number"
                    ? `${current.temperature_2m} °C`
                    : "—";
        }

        if (weatherConditionText) {
            weatherConditionText.textContent = getWeatherConditionText(current.weather_code);
        }

        if (weatherHumidityText) {
            weatherHumidityText.textContent =
                typeof current.relative_humidity_2m === "number"
                    ? `${current.relative_humidity_2m}%`
                    : "—";
        }

        if (weatherWindText) {
            weatherWindText.textContent =
                typeof current.wind_speed_10m === "number"
                    ? `${current.wind_speed_10m} km/h`
                    : "—";
        }

        weatherStatusText.textContent = "Weather updated";
    } catch (error) {
        console.error("Weather error:", error);
        weatherStatusText.textContent = "Error loading weather";
    }
}

function getWeatherConditionText(code) {
    const weatherCodeMap = {
        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Depositing rime fog",
        51: "Light drizzle",
        53: "Moderate drizzle",
        55: "Dense drizzle",
        61: "Slight rain",
        63: "Moderate rain",
        65: "Heavy rain",
        71: "Slight snow",
        73: "Moderate snow",
        75: "Heavy snow",
        80: "Slight rain showers",
        81: "Moderate rain showers",
        82: "Violent rain showers",
        95: "Thunderstorm"
    };

    return weatherCodeMap[code] || "Unknown";
}

function setVoiceStatus(text) {
    if (voiceStatusText) {
        voiceStatusText.textContent = text;
    }
}

function clearLastRecordedAudioUrl() {
    if (lastRecordedAudioUrl) {
        try {
            URL.revokeObjectURL(lastRecordedAudioUrl);
        } catch (error) {
            console.error("Failed to revoke audio URL:", error);
        }
        lastRecordedAudioUrl = "";
    }
}

function setVoiceTranscriptContent(content) {
    if (!voiceTranscriptBox) {
        return;
    }

    voiceTranscriptBox.innerHTML = "";
    if (typeof content === "string") {
        voiceTranscriptBox.textContent = content;
        return;
    }

    if (content) {
        voiceTranscriptBox.appendChild(content);
    }
}

function setVoiceTranscript(text) {
    setVoiceTranscriptContent(text || "No voice recording yet.");
}

function supportsRealVoiceRecording() {
    return (
        typeof window !== "undefined" &&
        !!navigator.mediaDevices &&
        typeof navigator.mediaDevices.getUserMedia === "function" &&
        typeof window.MediaRecorder !== "undefined"
    );
}

function getPreferredAudioMimeType() {
    const mimeTypes = [
        "audio/webm;codecs=opus",
        "audio/webm",
        "audio/mp4",
        "video/mp4",
        "audio/mpeg"
    ];

    for (let i = 0; i < mimeTypes.length; i += 1) {
        const mimeType = mimeTypes[i];
        try {
            if (MediaRecorder.isTypeSupported(mimeType)) {
                return mimeType;
            }
        } catch (error) {
            console.error("Failed to test mime type:", error);
        }
    }

    return "";
}

function stopVoiceStreamTracks() {
    if (!mediaStream) {
        return;
    }

    const tracks = mediaStream.getTracks();
    tracks.forEach(track => {
        try {
            track.stop();
        } catch (error) {
            console.error("Failed to stop media track:", error);
        }
    });

    mediaStream = null;
}

function renderRecordedAudioPreview() {
    if (!lastRecordedAudioBlob || !lastRecordedAudioUrl) {
        setVoiceTranscript("No voice recording yet.");
        return;
    }

    const wrapper = document.createElement("div");

    const text = document.createElement("div");
    text.textContent = `Voice recorded successfully. Size: ${Math.round(lastRecordedAudioBlob.size / 1024)} KB`;
    wrapper.appendChild(text);

    const audio = document.createElement("audio");
    audio.className = "voice-audio-player";
    audio.controls = true;
    audio.src = lastRecordedAudioUrl;
    wrapper.appendChild(audio);

    setVoiceTranscriptContent(wrapper);
}

function updateVoiceButtonsState() {
    if (startVoiceButton) {
        startVoiceButton.disabled = isVoiceRecording || !getAuthToken();
    }

    if (stopVoiceButton) {
        stopVoiceButton.disabled = !isVoiceRecording;
    }
}

function initVoiceRecording() {
    voiceRecordingSupported = supportsRealVoiceRecording();

    if (!voiceRecordingSupported) {
        setVoiceStatus("Microphone recording is not supported on this device.");
        setVoiceTranscript("No voice recording yet.");
        updateVoiceButtonsState();
        return;
    }

    setVoiceStatus("Microphone is ready.");
    setVoiceTranscript("No voice recording yet.");
    updateVoiceButtonsState();
}

async function startVoiceInput() {
    if (!voiceRecordingSupported) {
        setVoiceStatus("Microphone recording is not supported on this device.");
        return;
    }

    if (!getAuthToken()) {
        setVoiceStatus("Please log in on the Account tab to use voice input.");
        return;
    }

    if (isVoiceRecording) {
        return;
    }

    try {
        clearLastRecordedAudioUrl();
        lastRecordedAudioBlob = null;
        lastRecordedAudioMimeType = "";
        recordedAudioChunks = [];

        mediaStream = await navigator.mediaDevices.getUserMedia({
            audio: true
        });

        const preferredMimeType = getPreferredAudioMimeType();
        const mediaRecorderOptions = preferredMimeType ? { mimeType: preferredMimeType } : {};

        mediaRecorder = new MediaRecorder(mediaStream, mediaRecorderOptions);
        lastRecordedAudioMimeType = preferredMimeType || mediaRecorder.mimeType || "audio/webm";

        mediaRecorder.onstart = function () {
            isVoiceRecording = true;
            setVoiceStatus("Recording voice...");
            setVoiceTranscript("Recording in progress...");
            updateVoiceButtonsState();
        };

        mediaRecorder.ondataavailable = function (event) {
            if (event.data && event.data.size > 0) {
                recordedAudioChunks.push(event.data);
            }
        };

        mediaRecorder.onerror = function (event) {
            console.error("MediaRecorder error:", event);
            isVoiceRecording = false;
            setVoiceStatus("Voice recording failed: " + (event.error ? event.error.name : "unknown error"));
            updateVoiceButtonsState();
            stopVoiceStreamTracks();
        };

        mediaRecorder.onstop = function () {
            isVoiceRecording = false;

            try {
                const audioBlob = new Blob(recordedAudioChunks, {
                    type: lastRecordedAudioMimeType || "audio/webm"
                });

                if (audioBlob.size > 0) {
                    lastRecordedAudioBlob = audioBlob;
                    lastRecordedAudioUrl = URL.createObjectURL(audioBlob);
                    renderRecordedAudioPreview();
                    setVoiceStatus("Voice recording completed.");

                    sendAudioToServer(audioBlob);
                } else {
                    lastRecordedAudioBlob = null;
                    setVoiceTranscript("No audio was captured.");
                    setVoiceStatus("Voice recording completed, but no audio was captured.");
                }
            } catch (error) {
                console.error("Failed to finalize voice recording:", error);
                setVoiceStatus("Could not process recorded audio: " + (error.message || "unknown"));
                setVoiceTranscript("Recorded audio could not be processed.");
            }

            recordedAudioChunks = [];
            updateVoiceButtonsState();
            stopVoiceStreamTracks();
        };

        mediaRecorder.start();
    } catch (error) {
        console.error("Failed to start microphone recording:", error);

        isVoiceRecording = false;
        updateVoiceButtonsState();
        stopVoiceStreamTracks();

        if (error && error.name === "NotAllowedError") {
            setVoiceStatus("Microphone permission was denied.");
        } else if (error && error.name === "NotFoundError") {
            setVoiceStatus("No microphone was found on this device.");
        } else if (error && error.name === "NotReadableError") {
            setVoiceStatus("Microphone is already in use or not readable.");
        } else {
            setVoiceStatus("Could not start microphone recording: " + (error.message || "unknown"));
        }

        setVoiceTranscript("No voice recording yet.");
    }
}

function stopVoiceInput() {
    if (!mediaRecorder || !isVoiceRecording) {
        return;
    }

    try {
        mediaRecorder.stop();
        setVoiceStatus("Stopping voice recording...");
    } catch (error) {
        console.error("Failed to stop microphone recording:", error);
        setVoiceStatus("Could not stop voice recording: " + (error.message || "unknown"));
    }
}

async function sendAudioToServer(audioBlob) {
    try {
        if (!audioBlob || audioBlob.size === 0) {
            setVoiceStatus("No audio captured");
            return;
        }

        if (!getAuthToken()) {
            setVoiceStatus("Please log in on the Account tab to use voice input.");
            return;
        }

        const formData = new FormData();
        formData.append("audio", audioBlob, "voice.webm");

        setVoiceStatus("Processing voice...");

        const response = await authorizedFetch("/transcribe-voice", {
            method: "POST",
            body: formData
        });

        let data;
        try {
            data = await response.json();
        } catch (e) {
            setVoiceStatus("Invalid server response (could not parse JSON).");
            return;
        }

        if (!response.ok) {
            /* Show the actual server error — quota, MIME, auth, provider. */
            const serverMsg = (data && (data.message || data.error)) || `Server error (HTTP ${response.status})`;
            setVoiceStatus("Voice processing failed: " + serverMsg);
            return;
        }

        if (!data || data.status !== "success") {
            setVoiceStatus((data && data.message) || "Voice processing failed");
            return;
        }

        const transcribedText = String(data.text || "").trim();

        if (!transcribedText) {
            setVoiceStatus("No speech detected");
            return;
        }

        if (messageInput) {
            messageInput.value = transcribedText;
            messageInput.focus();
        }

        setVoiceTranscript(transcribedText);
        setVoiceStatus("Voice converted to text. Sending...");

        await sendMessage(true);

        setVoiceStatus("Voice converted and sent");
    } catch (error) {
        console.error("Failed to convert voice to text:", error);
        setVoiceStatus("Voice conversion failed: " + (error.message || "network error"));
    }
}

function startReminderAutoRefresh() {
    if (!getAuthToken()) {
        return;
    }

    if (reminderAutoRefreshIntervalId) {
        return;
    }

    reminderAutoRefreshIntervalId = window.setInterval(() => {
        loadReminders({ silent: true });
    }, AUTO_REMINDER_INTERVAL_MS);
}

function stopReminderAutoRefresh() {
    if (reminderAutoRefreshIntervalId) {
        window.clearInterval(reminderAutoRefreshIntervalId);
        reminderAutoRefreshIntervalId = null;
    }
}

async function loadTasks() {
    if (!tasksList) {
        return;
    }

    tasksList.innerHTML = `<div class="loading">Loading tasks...</div>`;

    const res = await authorizedFetch("/tasks");
    const data = await res.json();

    if (!data.tasks || !Array.isArray(data.tasks)) {
        tasksList.innerHTML = `<div class="loading">Could not load tasks.</div>`;
        return;
    }

    renderTasks(data.tasks);
}

async function loadAppointments() {
    if (!appointmentsList) {
        return;
    }

    appointmentsList.innerHTML = `<div class="loading">Loading appointments...</div>`;

    const res = await authorizedFetch("/appointments");
    const data = await res.json();

    if (!data.appointments || !Array.isArray(data.appointments)) {
        appointmentsList.innerHTML = `<div class="loading">Could not load appointments.</div>`;
        return;
    }

    renderAppointments(data.appointments);
}

async function loadReminders(options = {}) {
    const { silent = false } = options;

    if (!remindersList) {
        return;
    }

    if (!getAuthToken()) {
        remindersList.innerHTML = `<div class="loading">No reminders right now.</div>`;
        return;
    }

    if (isLoadingReminders) {
        return;
    }

    isLoadingReminders = true;

    if (!silent) {
        remindersList.innerHTML = `<div class="loading">Loading reminders...</div>`;
    }

    try {
        const res = await authorizedFetch("/reminders");
        const data = await res.json();

        if (data.status !== "success") {
            remindersList.innerHTML = `<div class="loading">Could not load reminders.</div>`;
            return;
        }

        const tasks = data.tasks || [];
        const appointments = data.appointments || [];
        const nextSignature = buildReminderSignature(tasks, appointments);

        if (nextSignature === lastReminderSignature && silent) {
            return;
        }

        lastReminderSignature = nextSignature;
        renderReminders(tasks, appointments);
    } catch (error) {
        console.error("Failed to load reminders:", error);
        remindersList.innerHTML = `<div class="loading">Could not load reminders.</div>`;
    } finally {
        isLoadingReminders = false;
    }
}

async function loadExchangeRates() {
    if (!exchangeRatesStatusText) return;

    exchangeRatesStatusText.textContent = "Loading exchange rates...";

    try {
        const res = await fetch("/exchange-rates");
        const data = await res.json();

        if (data.status !== "success") {
            exchangeRatesStatusText.textContent = "Failed to load exchange rates";
            return;
        }

        const rates = data.rates || {};

        exchangeRatesBaseText.textContent = data.base || "USD";
        exchangeRateEurText.textContent = rates.EUR || "—";
        exchangeRateGbpText.textContent = rates.GBP || "—";
        exchangeRateCadText.textContent = rates.CAD || "—";
        exchangeRateTryText.textContent = rates.TRY || "—";
        exchangeRateAedText.textContent = rates.AED || "—";
        exchangeRatesUpdatedText.textContent = data.updated || "—";

        exchangeRatesStatusText.textContent = "Exchange rates updated";
    } catch (error) {
        console.error("Exchange rates error:", error);
        exchangeRatesStatusText.textContent = "Error loading exchange rates";
    }
}

function findCustomCurrency() {
    const input = (customCurrencyInput.value || "").trim().toUpperCase();

    if (!input) {
        customCurrencyResultText.textContent = "Please enter a currency";
        return;
    }

    customCurrencyResultText.textContent = "Loading...";

    fetch("/exchange-rates")
        .then(response => response.json())
        .then(data => {
            if (data.status !== "success") {
                customCurrencyResultText.textContent = "Error loading rates";
                return;
            }

            const rates = data.rates || {};

            if (rates[input]) {
                customCurrencyResultText.textContent = `USD → ${input}: ${rates[input]}`;
                return;
            }

            const countryMap = {
                JAPAN: "JPY",
                IRAN: "IRR",
                TURKEY: "TRY",
                UK: "GBP",
                ENGLAND: "GBP",
                EUROPE: "EUR",
                CANADA: "CAD",
                UAE: "AED",
                EMIRATES: "AED"
            };

            const currencyCode = countryMap[input];

            if (currencyCode && rates[currencyCode]) {
                customCurrencyResultText.textContent = `USD → ${currencyCode}: ${rates[currencyCode]}`;
                return;
            }

            customCurrencyResultText.textContent = "Currency not found";
        })
        .catch(error => {
            console.error("Custom currency error:", error);
            customCurrencyResultText.textContent = "Error loading currency";
        });
}

async function loadAppInfo() {
    /* Update the about card on the Home tab with server-side app info. */
    const aboutVersionEl = document.getElementById("aboutVersion");
    const aboutAuthorEl = document.getElementById("aboutAuthor");
    const aboutDescriptionEl = document.getElementById("aboutDescription");

    try {
        const res = await fetch("/app-info");
        const data = await res.json();

        if (aboutVersionEl) {
            aboutVersionEl.textContent = data.version || "1.1.0";
        }
        if (aboutAuthorEl) {
            aboutAuthorEl.textContent = data.author || "Amin Azimi";
        }
        if (aboutDescriptionEl) {
            aboutDescriptionEl.textContent = data.description || "A smart productivity assistant.";
        }
    } catch (error) {
        console.error("Failed to load app info:", error);
    }
}

/* =========================
   QUOTA — GET /api/v1/account/quota
   ========================= */

async function loadQuota() {
    if (!getAuthToken()) {
        if (quotaPlanText) quotaPlanText.textContent = "—";
        if (quotaLimitText) quotaLimitText.textContent = "—";
        if (quotaUsedText) quotaUsedText.textContent = "—";
        if (quotaRemainingText) quotaRemainingText.textContent = "—";
        if (quotaStatusText) quotaStatusText.textContent = "Not logged in";
        return;
    }

    if (quotaStatusText) quotaStatusText.textContent = "Loading quota...";

    try {
        const res = await authorizedFetch("/api/v1/account/quota");
        const data = await res.json();

        if (!res.ok) {
            if (quotaStatusText) {
                quotaStatusText.textContent = (data && data.message) || "Could not load quota";
            }
            return;
        }

        if (quotaPlanText) {
            quotaPlanText.textContent = data.plan_name || data.plan || "Free";
        }
        if (quotaLimitText) {
            quotaLimitText.textContent =
                data.ai_daily_limit != null ? String(data.ai_daily_limit) : "—";
        }
        if (quotaUsedText) {
            quotaUsedText.textContent =
                data.ai_calls_today != null ? String(data.ai_calls_today) : "—";
        }
        if (quotaRemainingText) {
            if (data.remaining != null) {
                quotaRemainingText.textContent = String(data.remaining);
            } else {
                quotaRemainingText.textContent = "Unlimited";
            }
        }
        if (quotaStatusText) {
            if (data.quota_exceeded) {
                quotaStatusText.textContent = "Daily quota exceeded — please try again tomorrow.";
            } else {
                quotaStatusText.textContent = "Active";
            }
        }
    } catch (error) {
        console.error("Failed to load quota:", error);
        if (quotaStatusText) {
            quotaStatusText.textContent = "Could not load quota: " + (error.message || "network error");
        }
    }
}

async function signup() {
    const name = nameInput ? nameInput.value.trim() : "";
    const email = emailInput ? emailInput.value.trim() : "";
    const password = passwordInput ? passwordInput.value.trim() : "";

    if (!email || !password) {
        updateAuthStatus("Email and password required");
        return;
    }

    updateAuthStatus("Signing up...");

    try {
        const res = await fetch("/signup", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, email, password })
        });

        const data = await res.json();

        if (data.status === "success" && data.user && data.user.token) {
            setAuthToken(data.user.token);
            updateAuthStatus("Signup successful and logged in");
            updateLoggedInUiState();
            startReminderAutoRefresh();
            loadTasks();
            loadAppointments();
            loadReminders();
            loadQuota();
            returnToPendingTab();
            return;
        }

        updateAuthStatus(data.message || "Signup failed");
    } catch (error) {
        updateAuthStatus("Signup failed");
        console.error("Signup failed:", error);
    }
}

async function login() {
    const email = emailInput ? emailInput.value.trim() : "";
    const password = passwordInput ? passwordInput.value.trim() : "";

    if (!email || !password) {
        updateAuthStatus("Email and password required");
        return;
    }

    updateAuthStatus("Logging in...");

    try {
        const res = await fetch("/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password })
        });

        const data = await res.json();

        if (data.status === "success" && data.user && data.user.token) {
            setAuthToken(data.user.token);
            updateAuthStatus("Logged in");
            updateLoggedInUiState();
            startReminderAutoRefresh();
            loadTasks();
            loadAppointments();
            loadReminders();
            loadQuota();
            returnToPendingTab();
            return;
        }

        updateAuthStatus(data.message || "Login failed");
    } catch (error) {
        updateAuthStatus("Login failed");
        console.error("Login failed:", error);
    }
}

/* After login, return to the tab the user was on when the 401 occurred. */
function returnToPendingTab() {
    if (pendingReturnTab) {
        showAppTab(pendingReturnTab);
        pendingReturnTab = null;
    }
}

async function logout() {
    try {
        await authorizedFetch("/logout", {
            method: "POST"
        });
    } catch (error) {
        console.error("Logout request failed:", error);
    }

    clearAuthToken();
    lastNotificationTimeMap = {};
    stopReminderAutoRefresh();
    lastReminderSignature = "";
    shownReminderIds = new Set();
    updateAuthStatus("Logged out");
    updateLoggedInUiState();

    if (tasksList) {
        tasksList.innerHTML = `<div class="loading">No tasks yet.</div>`;
    }

    if (appointmentsList) {
        appointmentsList.innerHTML = `<div class="loading">No appointments yet.</div>`;
    }

    if (remindersList) {
        remindersList.innerHTML = `<div class="loading">No reminders right now.</div>`;
    }

    if (quotaPlanText) quotaPlanText.textContent = "—";
    if (quotaLimitText) quotaLimitText.textContent = "—";
    if (quotaUsedText) quotaUsedText.textContent = "—";
    if (quotaRemainingText) quotaRemainingText.textContent = "—";
    if (quotaStatusText) quotaStatusText.textContent = "Not logged in";
}

async function createTaskFromMessage(message, dueDateValue) {
    const createRes = await authorizedFetch("/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            title: message,
            due_date: dueDateValue || null
        })
    });

    return await createRes.json();
}

async function updateTaskDueDate(taskId, dueDateValue) {
    const updateRes = await authorizedFetch(`/tasks/${taskId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            due_date: dueDateValue || null
        })
    });

    return await updateRes.json();
}

function renderReplyResult(replyText) {
    if (!resultBox) {
        return;
    }

    resultBox.textContent = replyText;
}

function renderTaskResult(taskData, actionLabel) {
    if (!resultBox) {
        return;
    }

    resultBox.textContent = JSON.stringify({
        status: "success",
        action: actionLabel,
        task: taskData
    }, null, 2);
}

async function sendMessage(isAuto = false) {
    const message = messageInput ? messageInput.value.trim() : "";
    const dueDateValue = dueDateInput ? dueDateInput.value : "";
    const dueTimeInputEl = document.getElementById("dueTimeInput");
    const dueTimeValue = dueTimeInputEl ? dueTimeInputEl.value : "";

    let finalDueDate = dueDateValue;
    if (dueDateValue && dueTimeValue) {
        finalDueDate = `${dueDateValue}T${dueTimeValue}:00`;
    }

    if (!getAuthToken()) {
        if (statusText) statusText.textContent = "Please log in first.";
        if (messageError) messageError.textContent = "Login required to send messages.";
        return;
    }

    if (!message) {
        if (statusText) statusText.textContent = "Please enter a message";
        return;
    }

    if (messageError) messageError.textContent = "";
    if (statusText) statusText.textContent = "Sending...";

    if (!isAuto) {
        await unlockReminderSound();
        await ensureBrowserNotificationPermission();
    }

    try {
        const res = await authorizedFetch("/smart-ai", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message })
        });

        let data;
        try {
            data = await res.json();
        } catch (e) {
            if (statusText) statusText.textContent = "Server error (invalid response)";
            return;
        }

        if (!res.ok || data.status !== "success") {
            const errMsg = data.message || data.error || "Request failed";
            if (statusText) statusText.textContent = errMsg;
            if (resultBox) resultBox.textContent = "Error: " + errMsg;
            return;
        }

        if (data.action === "reply") {
            renderReplyResult(data.reply || "No reply");
            if (statusText) statusText.textContent = "Done";
            return;
        }

        if (data.action === "task" && data.task) {
            let finalTask = data.task;

            if (finalDueDate && data.task.id) {
                try {
                    const updateData = await updateTaskDueDate(data.task.id, finalDueDate);
                    if (updateData && updateData.status === "success" && updateData.task) {
                        finalTask = updateData.task;
                    }
                } catch (e) {
                    console.warn("Due date update failed:", e);
                }
            }

            renderTaskResult(finalTask, "task");
            if (statusText) statusText.textContent = "Done";

            if (messageInput) messageInput.value = "";
            if (dueDateInput) dueDateInput.value = "";
            if (dueTimeInputEl) dueTimeInputEl.value = "";

            loadTasks();
            loadAppointments();
            loadReminders();
            loadQuota();
            return;
        }

        /* Fallback: show raw response */
        if (resultBox) resultBox.textContent = JSON.stringify(data, null, 2);
        if (statusText) statusText.textContent = "Done";
        loadTasks();
        loadAppointments();
        loadReminders();
        loadQuota();

    } catch (error) {
        console.error("sendMessage error:", error);
        if (statusText) statusText.textContent = "Send failed: " + (error.message || "network error");
        if (resultBox) resultBox.textContent = "Error: " + (error.message || "Send failed");
    }
}

async function updateTask(id, status) {
    await unlockReminderSound();
    await ensureBrowserNotificationPermission();

    await authorizedFetch(`/tasks/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status })
    });

    if (statusText) statusText.textContent = "Task updated";
    loadTasks();
    loadReminders();
}

async function deleteTask(id) {
    if (!confirm("Delete this task?")) {
        return;
    }

    await unlockReminderSound();
    await ensureBrowserNotificationPermission();

    await authorizedFetch(`/tasks/${id}`, {
        method: "DELETE"
    });

    if (statusText) statusText.textContent = "Task deleted";
    loadTasks();
    loadReminders();
}

if (sendButton) {
    sendButton.addEventListener("click", sendMessage);
}

/* ---- Manual task creation ---- */
async function createTaskManual() {
    const titleEl = document.getElementById("newTaskTitleInput");
    const descEl = document.getElementById("newTaskDescInput");
    const priorityEl = document.getElementById("newTaskPrioritySelect");
    const dueDateEl = document.getElementById("newTaskDueDateInput");
    const statusEl = document.getElementById("createTaskStatus");
    const titleErrorEl = document.getElementById("newTaskTitleError");

    const title = titleEl ? titleEl.value.trim() : "";
    if (!title) {
        if (titleErrorEl) titleErrorEl.textContent = "Title is required";
        if (statusEl) statusEl.textContent = "Title is required";
        return;
    }
    if (titleErrorEl) titleErrorEl.textContent = "";

    if (statusEl) statusEl.textContent = "Creating...";

    try {
        const body = {
            title,
            description: descEl ? descEl.value.trim() : "",
            priority: priorityEl ? priorityEl.value : "medium",
        };
        if (dueDateEl && dueDateEl.value) {
            body.due_date = dueDateEl.value;
        }

        const res = await authorizedFetch("/tasks", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });
        const data = await res.json();

        if (data.status === "success") {
            if (statusEl) statusEl.textContent = "Task created!";
            if (titleEl) titleEl.value = "";
            if (descEl) descEl.value = "";
            if (dueDateEl) dueDateEl.value = "";
            loadTasks();
            loadReminders();
        } else {
            if (statusEl) statusEl.textContent = data.message || "Failed to create task";
        }
    } catch (e) {
        if (statusEl) statusEl.textContent = "Error creating task: " + (e.message || "network error");
    }
}

/* ---- Manual appointment creation ---- */
async function createAppointmentManual() {
    const titleEl = document.getElementById("newApptTitleInput");
    const timeEl = document.getElementById("newApptTimeInput");
    const locationEl = document.getElementById("newApptLocationInput");
    const statusEl = document.getElementById("createApptStatus");
    const titleErrorEl = document.getElementById("newApptTitleError");
    const timeErrorEl = document.getElementById("newApptTimeError");

    const title = titleEl ? titleEl.value.trim() : "";
    const apptTime = timeEl ? timeEl.value : "";

    if (!title) {
        if (titleErrorEl) titleErrorEl.textContent = "Title is required";
        if (statusEl) statusEl.textContent = "Title is required";
        return;
    }
    if (titleErrorEl) titleErrorEl.textContent = "";

    if (!apptTime) {
        if (timeErrorEl) timeErrorEl.textContent = "Date & time is required";
        if (statusEl) statusEl.textContent = "Appointment time is required";
        return;
    }
    if (timeErrorEl) timeErrorEl.textContent = "";

    if (statusEl) statusEl.textContent = "Creating...";

    try {
        const res = await authorizedFetch("/appointments", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                title,
                appointment_time: apptTime,
                location: locationEl ? locationEl.value.trim() : "",
            }),
        });
        const data = await res.json();

        if (data.status === "success") {
            if (statusEl) statusEl.textContent = "Appointment created!";
            if (titleEl) titleEl.value = "";
            if (timeEl) timeEl.value = "";
            if (locationEl) locationEl.value = "";
            loadAppointments();
            loadReminders();
        } else {
            if (statusEl) statusEl.textContent = data.message || "Failed to create appointment";
        }
    } catch (e) {
        if (statusEl) statusEl.textContent = "Error creating appointment: " + (e.message || "network error");
    }
}

const createTaskButton = document.getElementById("createTaskButton");
if (createTaskButton) {
    createTaskButton.addEventListener("click", createTaskManual);
}

const createApptButton = document.getElementById("createApptButton");
if (createApptButton) {
    createApptButton.addEventListener("click", createAppointmentManual);
}

if (refreshTasksButton) {
    refreshTasksButton.addEventListener("click", async function () {
        await unlockReminderSound();
        await ensureBrowserNotificationPermission();
        loadTasks();
        loadAppointments();
        loadReminders();
    });
}

if (refreshRemindersButton) {
    refreshRemindersButton.addEventListener("click", async function () {
        await unlockReminderSound();
        await ensureBrowserNotificationPermission();
        loadReminders();
    });
}

if (refreshLocationButton) {
    refreshLocationButton.addEventListener("click", async function () {
        await unlockReminderSound();
        loadLiveLocation();
    });
}

if (refreshExchangeRatesButton) {
    refreshExchangeRatesButton.addEventListener("click", loadExchangeRates);
}

if (refreshWeatherButton) {
    refreshWeatherButton.addEventListener("click", async function () {
        await unlockReminderSound();
        await loadWeather();
    });
}

if (findCurrencyButton) {
    findCurrencyButton.addEventListener("click", findCustomCurrency);
}

if (startVoiceButton) {
    startVoiceButton.addEventListener("click", async function () {
        await unlockReminderSound();
        startVoiceInput();
    });
}

if (stopVoiceButton) {
    stopVoiceButton.addEventListener("click", async function () {
        await unlockReminderSound();
        stopVoiceInput();
    });
}

if (togglePasswordButton) {
    togglePasswordButton.addEventListener("click", togglePasswordVisibility);
}

if (signupButton) {
    signupButton.addEventListener("click", async function () {
        await unlockReminderSound();
        await ensureBrowserNotificationPermission();
        signup();
    });
}

if (loginButton) {
    loginButton.addEventListener("click", async function () {
        await unlockReminderSound();
        await ensureBrowserNotificationPermission();
        login();
    });
}

if (logoutButton) {
    logoutButton.addEventListener("click", async function () {
        await unlockReminderSound();
        await ensureBrowserNotificationPermission();
        logout();
    });
}

if (refreshQuotaButton) {
    refreshQuotaButton.addEventListener("click", async function () {
        await unlockReminderSound();
        loadQuota();
    });
}

document.addEventListener("visibilitychange", function () {
    if (document.hidden) {
        stopReminderAutoRefresh();
        return;
    }

    if (getAuthToken()) {
        loadReminders({ silent: true });
        startReminderAutoRefresh();
    }
});

ensureReminderUiStyle();
installReminderSoundUnlockListeners();
updateLoggedInUiState();
restoreCachedLocation();
initVoiceRecording();
updateVoiceButtonsState();

if (getAuthToken()) {
    startReminderAutoRefresh();
}

loadTasks();
loadAppointments();
loadReminders();
loadAppInfo();
loadExchangeRates();
loadQuota();

loadWeather();


function updateDateTime() {
    const now = new Date();

    const time = now.toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit"
    });

    const date = now.toLocaleDateString([], {
        weekday: "short",
        year: "numeric",
        month: "short",
        day: "numeric"
    });

    const timeEl = document.getElementById("digitalTimeText");
    const dateEl = document.getElementById("digitalDateText");

    if (timeEl) timeEl.textContent = time;
    if (dateEl) dateEl.textContent = date;
}

setInterval(updateDateTime, 1000);
updateDateTime();

function updateSmartGreeting() {
    const greetingText = document.getElementById("smartGreetingText");
    const greetingSubText = document.getElementById("smartGreetingSubText");

    if (!greetingText || !greetingSubText) {
        return;
    }

    const hour = new Date().getHours();

    if (hour >= 5 && hour < 12) {
        greetingText.textContent = "Good morning";
        greetingSubText.textContent = "Welcome back. Hope you have a productive morning.";
    } else if (hour >= 12 && hour < 17) {
        greetingText.textContent = "Good afternoon";
        greetingSubText.textContent = "Welcome back. Your assistant is ready to help.";
    } else if (hour >= 17 && hour < 21) {
        greetingText.textContent = "Good evening";
        greetingSubText.textContent = "Welcome back. Let's organize the rest of your day.";
    } else {
        greetingText.textContent = "Good night";
        greetingSubText.textContent = "Welcome back. I'm here whenever you need me.";
    }
}

updateSmartGreeting();

/* =========================
   TAB SWITCHING
   ========================= */

function showAppTab(tabName) {
    const tabButtons = document.querySelectorAll(".bottom-nav-item");
    const tabSections = document.querySelectorAll("[data-tab-section]");

    tabSections.forEach(section => {
        section.classList.toggle("is-hidden", section.dataset.tabSection !== tabName);
    });

    tabButtons.forEach(button => {
        button.classList.toggle("active", button.dataset.tab === tabName);
    });

    /* Refresh data when switching to relevant tabs */
    if (tabName === "account" && getAuthToken()) {
        loadQuota();
    }
    if (tabName === "ai") {
        updateSendButtonState();
        updateVoiceButtonsState();
    }

    window.scrollTo({
        top: 0,
        behavior: "smooth"
    });
}

document.querySelectorAll(".bottom-nav-item").forEach(button => {
    button.addEventListener("click", function () {
        showAppTab(button.dataset.tab || "home");
    });
});

showAppTab("home");
