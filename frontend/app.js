// Application State
let token = localStorage.getItem("stellar_jwt_token") || null;
let username = localStorage.getItem("stellar_username") || null;
let sessionId = localStorage.getItem("stellar_session_id") || null;

// DOM Cache
const healthText = document.getElementById("health-text");
const authLoggedOut = document.getElementById("auth-status-logged-out");
const authLoggedIn = document.getElementById("auth-status-logged-in");
const authUsernameField = document.getElementById("auth-username");
const authPasswordField = document.getElementById("auth-password");
const currentUserName = document.getElementById("current-user-name");
const displaySessionId = document.getElementById("display-session-id");

const messagesContainer = document.getElementById("messages-container");
const chatInput = document.getElementById("chat-input");
const chatSendBtn = document.getElementById("chat-send-btn");
const typingIndicator = document.getElementById("typing-indicator");

// Diagnostics panel
const similarityPanel = document.getElementById("similarity-panel");
const simBarsContainer = document.getElementById("sim-bars-container");
const metricChunks = document.getElementById("metric-chunks");
const metricTokens = document.getElementById("metric-tokens");
const metricModel = document.getElementById("metric-model");

// Overlay Modals
const docViewerModal = document.getElementById("doc-viewer-modal");
const docListContainer = document.getElementById("doc-list-container");
const toast = document.getElementById("toast");
const toastMessage = document.getElementById("toast-message");

// Initialize on DOM load
window.addEventListener("DOMContentLoaded", () => {
    if (!sessionId) {
        generateNewSessionId();
    } else {
        displaySessionId.innerText = sessionId;
    }
    
    checkSystemHealth();
    setInterval(checkSystemHealth, 30000);
    
    updateUIState();
});

// Generate Random Session ID
function generateNewSessionId() {
    const rand = Math.random().toString(36).substring(2, 10);
    sessionId = `sess_${rand}`;
    localStorage.setItem("stellar_session_id", sessionId);
    if (displaySessionId) displaySessionId.innerText = sessionId;
}

// Check Backend Health
async function checkSystemHealth() {
    try {
        const response = await fetch("/health");
        if (response.ok) {
            const data = await response.json();
            healthText.innerText = "Online";
            healthText.style.color = "var(--success-green)";
        } else {
            throw new Error();
        }
    } catch (e) {
        healthText.innerText = "Offline";
        healthText.style.color = "var(--danger-red)";
    }
}

// Update UI view based on token state
function updateUIState() {
    if (token && username) {
        authLoggedOut.classList.add("hidden");
        authLoggedIn.classList.remove("hidden");
        currentUserName.innerText = username;
        displaySessionId.innerText = sessionId;
        
        chatInput.removeAttribute("disabled");
        chatInput.placeholder = "Enter question here...";
        chatSendBtn.removeAttribute("disabled");
    } else {
        authLoggedOut.classList.remove("hidden");
        authLoggedIn.classList.add("hidden");
        
        chatInput.setAttribute("disabled", "true");
        chatInput.placeholder = "Please log in first...";
        chatSendBtn.setAttribute("disabled", "true");
        
        similarityPanel.classList.add("hidden");
        resetChatMessages();
    }
}

// Register user
async function handleRegister() {
    const u = authUsernameField.value.trim();
    const p = authPasswordField.value;
    
    if (!u || !p) {
        showToast("Username and password are required.");
        return;
    }
    
    try {
        const res = await fetch("/api/auth/register", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username: u, password: p })
        });
        
        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.detail || "Registration failed.");
        }
        
        showToast("Registration successful! You can now log in.", "success");
        authPasswordField.value = "";
    } catch (e) {
        showToast(e.message);
    }
}

// Log in user
async function handleLogin() {
    const u = authUsernameField.value.trim();
    const p = authPasswordField.value;
    
    if (!u || !p) {
        showToast("Username and password are required.");
        return;
    }
    
    try {
        const res = await fetch("/api/auth/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username: u, password: p })
        });
        
        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.detail || "Login failed.");
        }
        
        token = data.access_token;
        username = data.username;
        localStorage.setItem("stellar_jwt_token", token);
        localStorage.setItem("stellar_username", username);
        
        authUsernameField.value = "";
        authPasswordField.value = "";
        
        showToast(`Logged in as ${username}`, "success");
        updateUIState();
    } catch (e) {
        showToast(e.message);
    }
}

// Quick Guest Session Generator
async function autoRegisterGuest() {
    const rand = Math.floor(1000 + Math.random() * 9000);
    const guestUser = `student_${rand}`;
    const guestPass = `pass_${rand}`;
    
    try {
        // Register
        let res = await fetch("/api/auth/register", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username: guestUser, password: guestPass })
        });
        
        if (!res.ok) throw new Error("Auto-register failed.");
        
        // Login
        res = await fetch("/api/auth/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username: guestUser, password: guestPass })
        });
        
        const data = await res.json();
        if (!res.ok) throw new Error("Auto-login failed.");
        
        token = data.access_token;
        username = data.username;
        localStorage.setItem("stellar_jwt_token", token);
        localStorage.setItem("stellar_username", username);
        
        showToast(`Logged in as workspace guest: ${username}`, "success");
        updateUIState();
    } catch (e) {
        showToast(e.message);
    }
}

// Log out user
function handleLogout() {
    token = null;
    username = null;
    localStorage.removeItem("stellar_jwt_token");
    localStorage.removeItem("stellar_username");
    generateNewSessionId();
    showToast("Logged out successfully.", "success");
    updateUIState();
}

// New chat session
function createNewSession() {
    generateNewSessionId();
    resetChatMessages();
    similarityPanel.classList.add("hidden");
    showToast("New chat session initialized.", "success");
}

// Reset chat window messages
function resetChatMessages() {
    messagesContainer.innerHTML = `
        <div class="system-message" id="welcome-box">
            <p><strong>System Note:</strong> Please log in or click <strong>"Quick Guest Start"</strong> to initialize a JWT token session.</p>
            <p>Once authenticated, the assistant will answer questions using cosine similarity retrieval from <code>docs.json</code>. If a question is out of scope (similarity score falls below the 0.35 threshold), a safe grounding fallback is returned.</p>
            <p class="suggestions-title"><strong>Sample Queries to Try:</strong></p>
            <ul class="suggestions-list">
                <li><a href="#" onclick="useSuggestedQuery('How can I reset my password?')">How do I reset my password?</a></li>
                <li><a href="#" onclick="useSuggestedQuery('What is the guest Wi-Fi SSID and password?')">What is the guest Wi-Fi credentials?</a></li>
                <li><a href="#" onclick="useSuggestedQuery('What is the remote work policy?')">How does hybrid remote work operate?</a></li>
                <li><a href="#" onclick="useSuggestedQuery('What is the refund policy?')">How many days do I have to request a billing refund?</a></li>
                <li><a href="#" onclick="useSuggestedQuery('Who is the president of the United States?')">Who is the president of the US? (Trigger Grounding Fallback)</a></li>
            </ul>
        </div>
    `;
}

// Clear history on database
async function clearCurrentChat() {
    if (!token) return;
    try {
        const res = await fetch("/api/chat/clear", {
            method: "POST",
            headers: { 
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify({ sessionId: sessionId, message: "clear" })
        });
        
        if (res.ok) {
            resetChatMessages();
            similarityPanel.classList.add("hidden");
            showToast("Chat history cleared on DB.", "success");
        }
    } catch (e) {
        showToast(e.message);
    }
}

// Trigger query chip clicks
function useSuggestedQuery(query) {
    chatInput.value = query;
    handleSendMessage();
}

// Appends message to DOM
function appendMessage(role, text) {
    const welcome = document.getElementById("welcome-box");
    if (welcome) welcome.remove();
    
    const row = document.createElement("div");
    row.className = `message-row ${role}-row`;
    
    const bubble = document.createElement("div");
    bubble.className = "message-bubble";
    
    if (role === "assistant") {
        bubble.innerHTML = parseMarkdown(text);
    } else {
        bubble.innerText = text;
    }
    
    row.appendChild(bubble);
    messagesContainer.appendChild(row);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// Sends user message to API
async function handleSendMessage(e) {
    if (e) e.preventDefault();
    
    const msg = chatInput.value.trim();
    if (!msg || !token) return;
    
    chatInput.value = "";
    chatInput.setAttribute("disabled", "true");
    chatSendBtn.setAttribute("disabled", "true");
    
    appendMessage("user", msg);
    
    typingIndicator.classList.remove("hidden");
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    
    try {
        const res = await fetch("/api/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify({ sessionId: sessionId, message: msg })
        });
        
        const data = await res.json();
        
        if (!res.ok) {
            throw new Error(data.detail || "Error communicating with server.");
        }
        
        typingIndicator.classList.add("hidden");
        appendMessage("assistant", data.reply);
        
        // Update diagnostics
        metricChunks.innerText = data.retrievedChunks;
        metricTokens.innerText = data.tokensUsed;
        metricModel.innerText = data.modelName;
        
        renderScoresList(data.similarityScores);
        
    } catch (err) {
        typingIndicator.classList.add("hidden");
        showToast(err.message);
        appendMessage("assistant", `⚠️ **Error**: ${err.message}`);
    } finally {
        chatInput.removeAttribute("disabled");
        chatSendBtn.removeAttribute("disabled");
        chatInput.focus();
    }
}

// Renders text similarity scores list
function renderScoresList(scores) {
    simBarsContainer.innerHTML = "";
    if (!scores || scores.length === 0) {
        similarityPanel.classList.add("hidden");
        return;
    }
    
    similarityPanel.classList.remove("hidden");
    scores.forEach((score, index) => {
        const li = document.createElement("li");
        
        let labelColor = "black";
        if (score >= 0.65) labelColor = "var(--success-green)";
        else if (score >= 0.35) labelColor = "var(--success-green)"; // acceptable matching
        else labelColor = "var(--danger-red)";
        
        li.innerHTML = `Chunk Match #${index + 1}: <strong style="color: ${labelColor}">${score.toFixed(4)}</strong>`;
        simBarsContainer.appendChild(li);
    });
}

// Toggle Documents List viewer
function toggleDocViewer() {
    if (docViewerModal.classList.contains("hidden")) {
        docViewerModal.classList.remove("hidden");
        fetchIndexedDocs();
    } else {
        docViewerModal.classList.add("hidden");
    }
}

// Fetch indexed documents list
async function fetchIndexedDocs() {
    if (!token) return;
    docListContainer.innerHTML = "<div class='loading-spinner'><i class='fa-solid fa-spinner fa-spin'></i> Loading...</div>";
    
    try {
        const res = await fetch("/api/docs", {
            headers: { "Authorization": `Bearer ${token}` }
        });
        
        if (!res.ok) throw new Error();
        
        const docs = await res.json();
        docListContainer.innerHTML = "";
        
        if (docs.length === 0) {
            docListContainer.innerHTML = "<p>No documents currently indexed.</p>";
            return;
        }
        
        docs.forEach(doc => {
            const card = document.createElement("div");
            card.className = "doc-card";
            card.innerHTML = `
                <h4>${escapeHTML(doc.title)}</h4>
                <p>${escapeHTML(doc.content)}</p>
            `;
            docListContainer.appendChild(card);
        });
    } catch (e) {
        docListContainer.innerHTML = "<p style='color:var(--danger-red);'>Failed to load documents.</p>";
    }
}

// Re-index defaults
async function reindexDefaultDocs() {
    if (!token) return;
    try {
        const res = await fetch("/api/docs/reindex-default", {
            method: "POST",
            headers: { "Authorization": `Bearer ${token}` }
        });
        
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to index.");
        
        showToast(`Indexed ${data.inserted_documents} documents (${data.total_chunks} chunks).`, "success");
    } catch (e) {
        showToast(e.message);
    }
}

// Simple Toast Notification
function showToast(message, type = "error") {
    toastMessage.innerText = message;
    toast.className = "toast";
    if (type === "success") {
        toast.style.backgroundColor = "var(--success-green)";
    } else {
        toast.style.backgroundColor = "#374151";
    }
    toast.classList.remove("hidden");
    
    setTimeout(() => {
        toast.classList.add("hidden");
    }, 3000);
}

// Escapes HTML tags
function escapeHTML(str) {
    return str
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Simple Markdown helper
function parseMarkdown(text) {
    let html = escapeHTML(text);
    
    html = html.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
    html = html.replace(/`([^`\n]+)`/g, '<code>$1</code>');
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');
    html = html.replace(/^(?:\s*-\s+)(.+)$/gm, '<li>$1</li>');
    html = html.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');
    html = html.replace(/\n\n/g, '</p><p>');
    html = html.replace(/\n/g, '<br>');
    
    if (!html.startsWith("<p>") && !html.startsWith("<pre>") && !html.startsWith("<ul>")) {
        html = `<p>${html}</p>`;
    }
    
    return html;
}
