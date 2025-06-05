// WebSocket connection
const ws = new WebSocket(`ws://${window.location.hostname}:${window.location.port}/ws`);

// Detection Controls
const startDetectionBtn = document.getElementById('start-detection');
const stopDetectionBtn = document.getElementById('stop-detection');
const confidenceThreshold = document.getElementById('confidence-threshold');
const confidenceValue = document.getElementById('confidence-value');
const detectionInterval = document.getElementById('detection-interval');
const intervalValue = document.getElementById('interval-value');

// Update value displays
confidenceThreshold.addEventListener('input', () => {
    confidenceValue.textContent = confidenceThreshold.value;
    sendDetectionSettings();
});

detectionInterval.addEventListener('input', () => {
    intervalValue.textContent = detectionInterval.value;
    sendDetectionSettings();
});

function sendDetectionSettings() {
    ws.send(JSON.stringify({
        type: 'detection_settings',
        confidence: parseFloat(confidenceThreshold.value),
        interval: parseInt(detectionInterval.value)
    }));
}

// Start/Stop Detection
startDetectionBtn.addEventListener('click', () => {
    ws.send(JSON.stringify({ type: 'control', command: 'start_detection' }));
    startDetectionBtn.disabled = true;
    stopDetectionBtn.disabled = false;
    addLogEntry('Detection started', 'info');
});

stopDetectionBtn.addEventListener('click', () => {
    ws.send(JSON.stringify({ type: 'control', command: 'stop_detection' }));
    startDetectionBtn.disabled = false;
    stopDetectionBtn.disabled = true;
    addLogEntry('Detection stopped', 'info');
});

// Mission Planning
const missionNameInput = document.getElementById('mission-name');
const waypointsInput = document.getElementById('waypoints');
const saveMissionBtn = document.getElementById('save-mission');
const executeMissionBtn = document.getElementById('execute-mission');

saveMissionBtn.addEventListener('click', () => {
    const mission = {
        name: missionNameInput.value,
        waypoints: waypointsInput.value.split('\n').map(line => {
            const [lat, lon] = line.split(',').map(n => parseFloat(n.trim()));
            return { lat, lon };
        })
    };
    
    ws.send(JSON.stringify({
        type: 'mission',
        command: 'save',
        data: mission
    }));
    
    addLogEntry(`Mission "${mission.name}" saved`, 'info');
});

executeMissionBtn.addEventListener('click', () => {
    const missionName = missionNameInput.value;
    ws.send(JSON.stringify({
        type: 'mission',
        command: 'execute',
        name: missionName
    }));
    
    addLogEntry(`Executing mission "${missionName}"`, 'info');
});

// Configuration Editor
const configSelect = document.getElementById('config-file');
const configEditor = document.getElementById('config-editor');
const saveConfigBtn = document.getElementById('save-config');

configSelect.addEventListener('change', () => {
    ws.send(JSON.stringify({
        type: 'config',
        command: 'load',
        file: configSelect.value
    }));
});

saveConfigBtn.addEventListener('click', () => {
    try {
        const config = JSON.parse(configEditor.value);
        ws.send(JSON.stringify({
            type: 'config',
            command: 'save',
            file: configSelect.value,
            data: config
        }));
        addLogEntry(`Configuration saved: ${configSelect.value}`, 'info');
    } catch (err) {
        addLogEntry(`Invalid JSON configuration: ${err.message}`, 'error');
    }
});

// Log Viewer
const logViewer = document.getElementById('log-viewer');
const logFilter = document.getElementById('log-filter');
const clearLogsBtn = document.getElementById('clear-logs');
const exportLogsBtn = document.getElementById('export-logs');

function addLogEntry(message, level = 'info') {
    const timestamp = new Date().toISOString();
    const entry = document.createElement('div');
    entry.className = `log-entry ${level}`;
    entry.textContent = `[${timestamp}] ${message}`;
    logViewer.appendChild(entry);
    logViewer.scrollTop = logViewer.scrollHeight;
}

logFilter.addEventListener('input', () => {
    const filter = logFilter.value.toLowerCase();
    const entries = logViewer.getElementsByClassName('log-entry');
    
    for (const entry of entries) {
        const text = entry.textContent.toLowerCase();
        entry.style.display = text.includes(filter) ? 'block' : 'none';
    }
});

clearLogsBtn.addEventListener('click', () => {
    logViewer.innerHTML = '';
    addLogEntry('Logs cleared', 'info');
});

exportLogsBtn.addEventListener('click', () => {
    const logs = Array.from(logViewer.getElementsByClassName('log-entry'))
        .map(entry => entry.textContent)
        .join('\n');
    
    const blob = new Blob([logs], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `flying-lora-logs-${new Date().toISOString()}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    addLogEntry('Logs exported', 'info');
});

// WebSocket message handling
ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    
    switch(data.type) {
        case 'config':
            configEditor.value = JSON.stringify(data.data, null, 2);
            break;
        case 'log':
            addLogEntry(data.message, data.level);
            break;
        case 'status':
            updateStatus(data);
            break;
    }
};

ws.onopen = function() {
    addLogEntry('Connected to server', 'info');
};

ws.onclose = function() {
    addLogEntry('Disconnected from server', 'error');
};

// Initialize everything when the page loads
window.addEventListener('load', () => {
    stopDetectionBtn.disabled = true;
    addLogEntry('Control panel initialized', 'info');
}); 