const API_BASE = '';
const API_KEY = 'vikingsofthenorth';
let currentSessionId = 'default_web';
let currentConfirmationId = null;

const chatHistory = document.getElementById('chat-history');
const chatInput = document.getElementById('chat-input');
const btnSend = document.getElementById('btn-send');
const btnNewTask = document.getElementById('btn-new-task');
const agentList = document.getElementById('agent-list');
const autopilotList = document.getElementById('autopilot-list');

// Modal elements
const modalOverlay = document.getElementById('confirmation-modal');
const modalContent = document.getElementById('confirmation-content');
const btnConfirm = document.getElementById('btn-confirm');
const btnCancel = document.getElementById('btn-cancel');

// Helper to make API calls
async function apiCall(endpoint, method = 'POST', body = null) {
    try {
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': API_KEY
            }
        };
        if (body) {
            options.body = JSON.stringify(body);
        }
        const res = await fetch(`${API_BASE}${endpoint}`, options);
        if (!res.ok) throw new Error(`API Error: ${res.statusText}`);
        return await res.json();
    } catch (error) {
        console.error('API Error:', error);
        appendMessage('system', 'Connection error. Please ensure the backend is running.');
        throw error;
    }
}

// Append message to chat UI
function appendMessage(sender, text, isTool = false) {
    const msgDiv = document.createElement('div');
    msgDiv.className = isTool ? 'tool-call' : `message ${sender}`;
    
    if (isTool) {
        msgDiv.innerText = `➜ Calling tool: ${text}`;
    } else {
        // Convert markdown to HTML using marked.js
        let htmlText = "";
        try {
            htmlText = marked.parse(text);
        } catch (e) {
            htmlText = text.replace(/\n/g, '<br>'); // fallback
        }
        msgDiv.innerHTML = htmlText;
        
        const meta = document.createElement('div');
        meta.className = 'message-meta';
        const time = new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
        meta.innerHTML = `<span>${sender === 'user' ? 'You' : 'Agent'}</span><span>${time}</span>`;
        msgDiv.appendChild(meta);
    }
    
    // Remove welcome message if present
    const welcome = document.querySelector('.welcome-message');
    if (welcome) welcome.remove();

    chatHistory.appendChild(msgDiv);
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

// Show or hide the thinking header
let thinkingContainerEl = null;

function showThinkingHeader() {
    if (thinkingContainerEl) return;
    thinkingContainerEl = document.createElement('div');
    thinkingContainerEl.className = 'thinking-container';
    thinkingContainerEl.innerHTML = `
        <div class="thinking-header">
            <span class="thinking-icon">⚙️</span>
            <span>Agent is thinking...</span>
        </div>
        <div class="thinking-logs"></div>
    `;
    chatHistory.appendChild(thinkingContainerEl);
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

function appendThinkingLog(text) {
    if (!thinkingContainerEl) return;
    const logsDiv = thinkingContainerEl.querySelector('.thinking-logs');
    const logEl = document.createElement('div');
    logEl.className = 'tool-call log-stream';
    logEl.textContent = `➜ Calling tool: ${text}`;
    logsDiv.appendChild(logEl);
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

function removeThinkingHeader() {
    if (thinkingContainerEl) {
        thinkingContainerEl.remove();
        thinkingContainerEl = null;
    }
}

// Handle sending a message
async function sendMessage() {
    const text = chatInput.value.trim();
    if (!text) return;
    
    appendMessage('user', text);
    chatInput.value = '';
    
    // Disable inputs and show loader
    chatInput.disabled = true;
    btnSend.disabled = true;
    showThinkingHeader();
    setTimeout(updateAgentList, 500); // Give backend time to flip the status bit before polling
    
    try {
        const response = await fetch(`${API_BASE}/agent/stream`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': API_KEY
            },
            body: JSON.stringify({
                message: text,
                session_id: currentSessionId
            })
        });

        if (!response.ok) {
            throw new Error(`API Error: ${response.statusText}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            
            let lines = buffer.split('\n\n');
            buffer = lines.pop(); // keep the last incomplete chunk in the buffer
            
            for (let line of lines) {
                if (line.startsWith('data: ')) {
                    const dataStr = line.substring(6);
                    try {
                        const data = JSON.parse(dataStr);
                        if (data.type === 'tool') {
                            appendThinkingLog(data.name);
                        } else if (data.type === 'done') {
                            const finalResponse = data.response;
                            removeThinkingHeader();
                            
                            // Log all actions taken
                            if (finalResponse.actions && finalResponse.actions.length > 0) {
                                finalResponse.actions.forEach(action => {
                                    appendMessage('system', action.tool, true);
                                });
                            }
                            
                            if (finalResponse.response) {
                                appendMessage('agent', finalResponse.response);
                            }
                            
                            if (finalResponse.requires_confirmation && finalResponse.confirmation_id) {
                                showConfirmationModal(finalResponse.confirmation_id, finalResponse.response);
                            }
                            
                            updateAgentList();
                        } else if (data.type === 'error') {
                            removeThinkingHeader();
                            throw new Error(data.error);
                        }
                    } catch(e) {
                        console.error('Error parsing stream data:', e);
                    }
                }
            }
        }
    } catch (e) {
        removeThinkingHeader();
        console.error(e);
        appendMessage('system', 'Connection error. Please ensure the backend is running.');
    } finally {
        // Re-enable inputs
        chatInput.disabled = false;
        btnSend.disabled = false;
        chatInput.focus();
    }
}

// Show Confirmation Modal
function showConfirmationModal(confirmationId, messageContext) {
    currentConfirmationId = confirmationId;
    modalContent.innerHTML = `<p>The agent is requesting permission to execute an action (e.g. send a message). Do you approve?</p>`;
    modalOverlay.classList.add('active');
}

// Handle Confirm
btnConfirm.addEventListener('click', async () => {
    if (!currentConfirmationId) return;
    
    modalOverlay.classList.remove('active');
    
    try {
        const result = await apiCall('/whatsapp/confirm', 'POST', {
            confirmation_id: currentConfirmationId
        });
        
        if (result.success) {
            appendMessage('system', 'Action confirmed and executed successfully.', true);
        } else {
            appendMessage('system', `Action failed: ${result.error}`, true);
        }
    } catch (e) {}
    
    currentConfirmationId = null;
});

// Handle Cancel
btnCancel.addEventListener('click', () => {
    modalOverlay.classList.remove('active');
    appendMessage('system', 'Action cancelled by user.', true);
    currentConfirmationId = null;
});

// Event Listeners
btnSend.addEventListener('click', sendMessage);
chatInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
});

// Fetch real Agent list from Coordinator
async function updateAgentList() {
    try {
        const data = await apiCall('/agent/list', 'GET');
        
        if (!data || !data.agents) return;
        
        agentList.innerHTML = '';
        data.agents.forEach(agent => {
            const li = document.createElement('li');
            li.className = 'agent-card active';
            
            // Add a pulsing animation if the agent is thinking
            const statusStyle = agent.status.includes('Thinking') ? 'color: var(--primary); font-weight: 500; animation: pulse 1.5s infinite;' : '';
            
            li.innerHTML = `
                <h4>${agent.name}</h4>
                <p style="${statusStyle}">${agent.status}</p>
            `;
            agentList.appendChild(li);
        });
    } catch (e) {
        console.error("Failed to fetch agent list", e);
    }
}

// Fetch real Autopilot list from Coordinator
async function updateAutopilotList() {
    if (!autopilotList) return;
    try {
        const data = await apiCall('/autopilot/list', 'GET');
        
        if (!data || !data.autopilots) return;
        
        autopilotList.innerHTML = '';
        data.autopilots.forEach(ap => {
            const li = document.createElement('li');
            li.className = 'agent-card';
            li.style.cursor = 'default';
            
            li.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                    <div>
                        <h4 style="margin-bottom: 4px;">${ap.contact}</h4>
                        <p style="font-size: 0.75rem; color: var(--text-secondary); margin-bottom: 4px;">Goal: ${ap.goal}</p>
                        <p style="font-size: 0.75rem; color: var(--text-secondary);">Until: ${new Date(ap.active_until).toLocaleTimeString()}</p>
                    </div>
                    <button class="btn" style="padding: 0.25rem 0.5rem; font-size: 0.75rem; background: var(--bg-tertiary); border: 1px solid var(--border-color); color: var(--text-primary); cursor: pointer;" onclick="revokeAutopilot('${ap.contact}')">Revoke</button>
                </div>
            `;
            autopilotList.appendChild(li);
        });
    } catch (e) {
        console.error("Failed to fetch autopilot list", e);
    }
}

// Revoke autopilot manually
window.revokeAutopilot = async function(contact) {
    if (!confirm(`Are you sure you want to revoke autopilot for ${contact}?`)) return;
    try {
        const data = await apiCall('/autopilot/disable', 'POST', { contact: contact });
        if (data && data.success) {
            updateAutopilotList();
        }
    } catch (e) {
        console.error("Failed to revoke autopilot", e);
        alert("Error revoking autopilot.");
    }
}

// Initial setup
updateAgentList();
updateAutopilotList();

// Create New Task Session
if (btnNewTask) {
    btnNewTask.addEventListener('click', () => {
        currentSessionId = 'web_session_' + Math.random().toString(36).substr(2, 9);
        
        // Clear chat
        const welcomeHtml = `
            <div class="welcome-message">
                <h2>New Context Established</h2>
                <p>I have completely cleared my short-term memory and started a fresh context for you (Session: ${currentSessionId}).</p>
            </div>
        `;
        chatHistory.innerHTML = welcomeHtml;
        
        appendMessage('system', 'Ready for a new task!', true);
    });
}

// Connect to Background Notification Stream
function connectNotificationStream() {
    // If API_BASE is empty (relative path), construct absolute URL for EventSource
    let sseUrl = `${API_BASE}/notifications/stream`;
    if (!API_BASE) {
        sseUrl = `/notifications/stream`;
    }
    // Add API key as query param since EventSource doesn't support custom headers
    sseUrl += `?api_key=${encodeURIComponent(API_KEY)}`;
    
    const evtSource = new EventSource(sseUrl);
    
    evtSource.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            
            if (data.type === "new_message") {
                appendMessage('system', `🔔 New background message detected from ${data.names}. Agent is reviewing it...`, true);
                showThinkingHeader();
                updateAgentList(); // Update status to Thinking
            } else if (data.type === "agent_thinking") {
                showThinkingHeader();
                updateAgentList(); // Update status to Thinking
            } else if (data.type === "tool") {
                appendThinkingLog(data.name);
                if (data.name === "whatsapp_manage_autopilot") {
                    setTimeout(updateAutopilotList, 500);
                }
            } else if (data.type === "agent_done") {
                const finalResponse = data.response;
                removeThinkingHeader();
                
                // Show tools
                if (finalResponse.actions && finalResponse.actions.length > 0) {
                    finalResponse.actions.forEach(action => {
                        appendMessage('system', `Background Tool: ${action.tool}`, true);
                    });
                }
                
                if (finalResponse.response) {
                    appendMessage('agent', `[Background Action]\n${finalResponse.response}`);
                }
                
                if (finalResponse.requires_confirmation && finalResponse.confirmation_id) {
                    showConfirmationModal(finalResponse.confirmation_id, finalResponse.response);
                }
                
                updateAgentList();
            }
        } catch (e) {
            console.error("Error parsing notification stream data:", e);
        }
    };
    
    evtSource.onerror = function(err) {
        console.error("EventSource failed:", err);
        // EventSource automatically reconnects on error.
    };
}

connectNotificationStream();
