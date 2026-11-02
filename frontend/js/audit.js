const API_BASE = '';
const API_KEY = 'vikingsofthenorth'; // Hardcoded for this demo

async function apiCall(endpoint, method = 'GET') {
    try {
        const options = {
            method,
            headers: {
                'X-API-Key': API_KEY
            }
        };
        const res = await fetch(`${API_BASE}${endpoint}`, options);
        if (!res.ok) throw new Error(`API Error: ${res.statusText}`);
        return await res.json();
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

function formatDate(isoString) {
    const d = new Date(isoString + 'Z'); // SQLite timestamps are UTC usually
    return d.toLocaleString([], {
        month: 'short', day: 'numeric',
        hour: '2-digit', minute:'2-digit', second:'2-digit'
    });
}

function syntaxHighlight(json) {
    if (!json) return '';
    if (typeof json != 'string') {
         json = JSON.stringify(json, null, 2);
    }
    // simple escape
    return json.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

async function fetchLogs() {
    const tbody = document.getElementById('audit-tbody');
    try {
        const logs = await apiCall('/audit/logs?limit=50');
        
        if (!logs || logs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-secondary);">No logs found.</td></tr>';
            return;
        }

        tbody.innerHTML = '';
        logs.forEach(log => {
            const tr = document.createElement('tr');
            
            // Timestamp
            const tdTime = document.createElement('td');
            tdTime.textContent = formatDate(log.created_at);
            
            // Tool Name
            const tdName = document.createElement('td');
            tdName.innerHTML = `<strong>${log.tool_name}</strong>`;
            
            // Status
            const tdStatus = document.createElement('td');
            if (log.error) {
                tdStatus.innerHTML = '<span class="badge badge-error">Error</span>';
            } else {
                tdStatus.innerHTML = '<span class="badge badge-success">Success</span>';
            }
            
            // Arguments
            const tdArgs = document.createElement('td');
            if (log.arguments) {
                tdArgs.innerHTML = `<pre class="json-block">${syntaxHighlight(log.arguments)}</pre>`;
            } else {
                tdArgs.textContent = '-';
            }
            
            // Result or Error
            const tdResult = document.createElement('td');
            if (log.error) {
                tdResult.innerHTML = `<div style="color: var(--danger); font-weight: 500;">${log.error}</div>`;
            } else if (log.result) {
                tdResult.innerHTML = `<pre class="json-block">${syntaxHighlight(log.result)}</pre>`;
            } else {
                tdResult.textContent = '-';
            }
            
            tr.appendChild(tdTime);
            tr.appendChild(tdName);
            tr.appendChild(tdStatus);
            tr.appendChild(tdArgs);
            tr.appendChild(tdResult);
            
            tbody.appendChild(tr);
        });
        
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--danger);">Failed to load logs: ${e.message}</td></tr>`;
    }
}

// Initial fetch
fetchLogs();
