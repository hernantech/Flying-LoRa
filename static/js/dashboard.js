// WebSocket connection
const ws = new WebSocket(`ws://${window.location.hostname}:${window.location.port}/ws`);

// Camera feed and detection overlay
const video = document.getElementById('live-feed');
const canvas = document.getElementById('detection-overlay');
const ctx = canvas.getContext('2d');

// Initialize camera feed
async function initCamera() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true });
        video.srcObject = stream;
    } catch (err) {
        console.error('Error accessing camera:', err);
    }
}

// Draw detection boxes
function drawDetections(detections) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.strokeStyle = '#00ff00';
    ctx.lineWidth = 2;
    
    detections.forEach(detection => {
        const { x, y, width, height, confidence, class: label } = detection;
        ctx.strokeRect(x, y, width, height);
        
        // Draw label
        ctx.fillStyle = '#00ff00';
        ctx.font = '14px Arial';
        ctx.fillText(`${label} ${(confidence * 100).toFixed(1)}%`, x, y - 5);
    });
}

// Initialize Three.js scene
let scene, camera, renderer;

function init3DVisualization() {
    scene = new THREE.Scene();
    camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
    renderer = new THREE.WebGLRenderer();
    
    const container = document.getElementById('three-container');
    renderer.setSize(container.clientWidth, container.clientHeight);
    container.appendChild(renderer.domElement);
    
    // Add basic grid
    const gridHelper = new THREE.GridHelper(10, 10);
    scene.add(gridHelper);
    
    camera.position.set(5, 5, 5);
    camera.lookAt(0, 0, 0);
}

// Performance metrics chart
let performanceChart;

function initPerformanceChart() {
    const ctx = document.getElementById('performance-chart').getContext('2d');
    performanceChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'FPS',
                data: [],
                borderColor: '#0d6efd',
                tension: 0.1
            }, {
                label: 'Latency (ms)',
                data: [],
                borderColor: '#dc3545',
                tension: 0.1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
}

// Initialize network map
let networkMap;

function initNetworkMap() {
    networkMap = L.map('network-map').setView([0, 0], 2);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(networkMap);
}

// Update network status
function updateNetworkStatus(data) {
    const signalStrength = document.getElementById('signal-strength');
    const networkQuality = document.getElementById('network-quality');
    
    signalStrength.style.width = `${data.signalStrength}%`;
    networkQuality.style.width = `${data.quality}%`;
}

// WebSocket message handling
ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    
    switch(data.type) {
        case 'detections':
            drawDetections(data.detections);
            break;
        case 'performance':
            updatePerformanceChart(data);
            break;
        case 'network':
            updateNetworkStatus(data);
            break;
        case 'position':
            update3DVisualization(data);
            break;
    }
};

// Initialize everything when the page loads
window.addEventListener('load', () => {
    initCamera();
    init3DVisualization();
    initPerformanceChart();
    initNetworkMap();
    
    // Handle window resize
    window.addEventListener('resize', () => {
        const container = document.getElementById('three-container');
        renderer.setSize(container.clientWidth, container.clientHeight);
        camera.aspect = container.clientWidth / container.clientHeight;
        camera.updateProjectionMatrix();
    });
});

// Animation loop for Three.js
function animate() {
    requestAnimationFrame(animate);
    renderer.render(scene, camera);
}
animate(); 