const chatWindow = document.getElementById("chat-window");
const userInput = document.getElementById("user-input");
const sendBtn = document.getElementById("send-btn");
const emergencyAlert = document.getElementById("emergency-alert");
const emergencyText = document.getElementById("emergency-text");

// Auth Elements
const authModal = document.getElementById("auth-modal");
const authUser = document.getElementById("auth-user");
const authPass = document.getElementById("auth-pass");
const authError = document.getElementById("auth-error");
const btnLogin = document.getElementById("btn-login");
const btnRegister = document.getElementById("btn-register");

const API_URL = "http://localhost:8000";

let userToken = localStorage.getItem("psikochat_token");

function checkAuth() {
    if (!userToken) {
        authModal.classList.remove("hidden");
    } else {
        authModal.classList.add("hidden");
        loadHistory();
    }
}

async function handleLogin() {
    const user = authUser.value.trim();
    const pass = authPass.value.trim();
    if (!user || !pass) {
        showError("Kullanıcı adı ve şifre gereklidir.");
        return;
    }

    try {
        const response = await fetch(`${API_URL}/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username: user, password: pass })
        });
        const data = await response.json();
        
        if (response.ok) {
            userToken = data.access_token;
            localStorage.setItem("psikochat_token", userToken);
            authModal.classList.add("hidden");
            loadHistory();
        } else {
            showError(data.detail || "Giriş başarısız.");
        }
    } catch (e) {
        showError("Sunucu bağlantı hatası.");
    }
}

async function handleRegister() {
    const user = authUser.value.trim();
    const pass = authPass.value.trim();
    if (!user || !pass) {
        showError("Kullanıcı adı ve şifre gereklidir.");
        return;
    }

    try {
        const response = await fetch(`${API_URL}/register`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username: user, password: pass })
        });
        const data = await response.json();
        
        if (response.ok) {
            // Auto login after register
            await handleLogin();
        } else {
            showError(data.detail || "Kayıt başarısız.");
        }
    } catch (e) {
        showError("Sunucu bağlantı hatası.");
    }
}

function showError(msg) {
    authError.innerText = msg;
    authError.classList.remove("hidden");
}

function scrollToBottom() {
    chatWindow.scrollTop = chatWindow.scrollHeight;
}

function appendMessage(text, sender, metaInfo = null) {
    const msgDiv = document.createElement("div");
    msgDiv.classList.add("message");
    msgDiv.classList.add(sender === "user" ? "user-message" : "system-message");
    
    let contentHtml = `<div>${text}</div>`;
    
    if (metaInfo) {
        contentHtml += `<div class="meta-tags">
            <span class="tag">Duygu: ${metaInfo.emotion}</span>
            <span class="tag">Risk: ${metaInfo.risk === "kriz" ? "Yüksek" : "Normal"}</span>
        </div>`;
    }

    msgDiv.innerHTML = contentHtml;
    chatWindow.appendChild(msgDiv);
    scrollToBottom();
}

function createTypingIndicator() {
    const msgDiv = document.createElement("div");
    msgDiv.classList.add("message", "system-message");
    msgDiv.id = "typing-indicator";
    msgDiv.innerHTML = `
        <div class="typing-indicator">
            <span></span><span></span><span></span>
        </div>
    `;
    chatWindow.appendChild(msgDiv);
    scrollToBottom();
}

function removeTypingIndicator() {
    const el = document.getElementById("typing-indicator");
    if (el) el.remove();
}

async function loadHistory() {
    if (!userToken) return;
    
    try {
        const response = await fetch(`${API_URL}/history`, {
            headers: { "Authorization": `Bearer ${userToken}` }
        });
        
        if (response.status === 401) {
            // Token expired or invalid
            localStorage.removeItem("psikochat_token");
            userToken = null;
            checkAuth();
            return;
        }

        if (response.ok) {
            const history = await response.json();
            // Clear existing static welcome message if history exists but leave it if empty
            if (history.length > 0) {
                chatWindow.innerHTML = "";
            }
            history.forEach(msg => {
                appendMessage(msg.text, msg.role === "user" ? "user" : "system");
            });
        }
    } catch (e) {
        console.error("Geçmiş yüklenemedi", e);
    }
}

async function sendMessage() {
    if (!userToken) {
        checkAuth();
        return;
    }

    const text = userInput.value.trim();
    if (!text) return;

    emergencyAlert.classList.add("hidden");
    appendMessage(text, "user");
    userInput.value = "";
    createTypingIndicator();

    try {
        const response = await fetch(`${API_URL}/predict`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${userToken}`
            },
            body: JSON.stringify({
                text: text,
                language: "tr"
            })
        });

        if (response.status === 401) {
            removeTypingIndicator();
            localStorage.removeItem("psikochat_token");
            userToken = null;
            checkAuth();
            return;
        }

        const data = await response.json();
        removeTypingIndicator();

        if (response.ok) {
            if (data.emergency_contact) {
                emergencyText.innerText = data.emergency_contact;
                emergencyAlert.classList.remove("hidden");
            }
            appendMessage(data.response, "system", { emotion: data.emotion, risk: data.risk });
        } else {
            console.error(data);
            appendMessage(data.detail || "Çok fazla mesaj attınız veya bir hata oluştu.", "system");
        }
    } catch (error) {
        console.error("Fetch Error:", error);
        removeTypingIndicator();
        appendMessage("Sunucuya bağlanılamadı. API hizmet vermiyor olabilir.", "system");
    }
}

// Event Listeners
sendBtn.addEventListener("click", sendMessage);
userInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") sendMessage();
});
btnLogin.addEventListener("click", handleLogin);
btnRegister.addEventListener("click", handleRegister);

// Init check
document.addEventListener("DOMContentLoaded", checkAuth);
