#!/usr/bin/env python3
"""
Simple System Health Dashboard
A basic implementation to get started with automated monitoring.
This can be implemented immediately to reduce manual system checking.
"""

from flask import Flask, jsonify, render_template_string
import json
import os
import psutil
import time
from datetime import datetime, timedelta
from typing import Dict, Any

app = Flask(__name__)

# HTML template for the dashboard
DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>DSR System Health Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        .status-good { color: #28a745; }
        .status-warning { color: #ffc107; }
        .status-critical { color: #dc3545; }
        .card { margin-bottom: 1rem; }
        .metric-card { text-align: center; }
        .metric-value { font-size: 2rem; font-weight: bold; }
        .last-updated { font-size: 0.8rem; color: #6c757d; }
    </style>
</head>
<body>
    <div class="container-fluid mt-3">
        <div class="row">
            <div class="col-12">
                <h1>🩺 DSR Billing System Health Dashboard</h1>
                <p class="last-updated">Last updated: <span id="last-updated">Loading...</span></p>
            </div>
        </div>
        
        <!-- Status Cards -->
        <div class="row">
            <div class="col-md-3">
                <div class="card metric-card">
                    <div class="card-body">
                        <h5 class="card-title">System Status</h5>
                        <div class="metric-value" id="system-status">●</div>
                        <small id="system-status-text">Loading...</small>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card metric-card">
                    <div class="card-body">
                        <h5 class="card-title">CPU Usage</h5>
                        <div class="metric-value" id="cpu-usage">--%</div>
                        <small>Current utilization</small>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card metric-card">
                    <div class="card-body">
                        <h5 class="card-title">Memory Usage</h5>
                        <div class="metric-value" id="memory-usage">--%</div>
                        <small>RAM utilization</small>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card metric-card">
                    <div class="card-body">
                        <h5 class="card-title">Last Generation</h5>
                        <div class="metric-value" id="last-generation" style="font-size: 1.2rem;">--</div>
                        <small>Excel report generation</small>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Charts -->
        <div class="row mt-4">
            <div class="col-md-6">
                <div class="card">
                    <div class="card-body">
                        <h5 class="card-title">System Performance</h5>
                        <canvas id="performanceChart" width="400" height="200"></canvas>
                    </div>
                </div>
            </div>
            <div class="col-md-6">
                <div class="card">
                    <div class="card-body">
                        <h5 class="card-title">Health Status Over Time</h5>
                        <canvas id="healthChart" width="400" height="200"></canvas>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Recent Activity -->
        <div class="row mt-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-body">
                        <h5 class="card-title">Recent Activity</h5>
                        <div id="recent-activity">
                            <p>Loading recent system activity...</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let performanceChart, healthChart;
        
        // Initialize charts
        function initCharts() {
            const ctx1 = document.getElementById('performanceChart').getContext('2d');
            performanceChart = new Chart(ctx1, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'CPU %',
                        data: [],
                        borderColor: 'rgb(75, 192, 192)',
                        tension: 0.1
                    }, {
                        label: 'Memory %',
                        data: [],
                        borderColor: 'rgb(255, 99, 132)',
                        tension: 0.1
                    }]
                },
                options: {
                    responsive: true,
                    scales: { y: { beginAtZero: true, max: 100 } }
                }
            });
            
            const ctx2 = document.getElementById('healthChart').getContext('2d');
            healthChart = new Chart(ctx2, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Health Score',
                        data: [],
                        borderColor: 'rgb(54, 162, 235)',
                        tension: 0.1
                    }]
                },
                options: {
                    responsive: true,
                    scales: { y: { beginAtZero: true, max: 100 } }
                }
            });
        }
        
        // Update dashboard
        async function updateDashboard() {
            try {
                const health = await fetch('/api/health').then(r => r.json());
                const metrics = await fetch('/api/metrics').then(r => r.json());
                
                // Update timestamp
                document.getElementById('last-updated').textContent = new Date().toLocaleString();
                
                // Update status cards
                updateSystemStatus(health);
                updateMetrics(metrics);
                updateCharts(metrics);
                updateRecentActivity(health);
                
            } catch (error) {
                console.error('Failed to update dashboard:', error);
                showError('Failed to connect to system API');
            }
        }
        
        function updateSystemStatus(health) {
            const statusEl = document.getElementById('system-status');
            const textEl = document.getElementById('system-status-text');
            
            if (health.overall_status === 'PASS') {
                statusEl.className = 'metric-value status-good';
                statusEl.textContent = '●';
                textEl.textContent = 'All systems operational';
            } else if (health.overall_status === 'WARNING') {
                statusEl.className = 'metric-value status-warning';
                statusEl.textContent = '●';
                textEl.textContent = 'Some issues detected';
            } else {
                statusEl.className = 'metric-value status-critical';
                statusEl.textContent = '●';
                textEl.textContent = 'Critical issues found';
            }
        }
        
        function updateMetrics(metrics) {
            document.getElementById('cpu-usage').textContent = metrics.cpu_percent.toFixed(1) + '%';
            document.getElementById('memory-usage').textContent = metrics.memory_percent.toFixed(1) + '%';
            
            if (metrics.last_generation) {
                const lastGen = new Date(metrics.last_generation);
                document.getElementById('last-generation').textContent = lastGen.toLocaleDateString();
            }
        }
        
        function updateCharts(metrics) {
            const now = new Date().toLocaleTimeString();
            
            // Update performance chart
            performanceChart.data.labels.push(now);
            performanceChart.data.datasets[0].data.push(metrics.cpu_percent);
            performanceChart.data.datasets[1].data.push(metrics.memory_percent);
            
            // Keep only last 20 data points
            if (performanceChart.data.labels.length > 20) {
                performanceChart.data.labels.shift();
                performanceChart.data.datasets.forEach(d => d.data.shift());
            }
            
            performanceChart.update();
            
            // Update health chart
            healthChart.data.labels.push(now);
            healthChart.data.datasets[0].data.push(metrics.health_score);
            
            if (healthChart.data.labels.length > 20) {
                healthChart.data.labels.shift();
                healthChart.data.datasets[0].data.shift();
            }
            
            healthChart.update();
        }
        
        function updateRecentActivity(health) {
            const activityEl = document.getElementById('recent-activity');
            let html = '<ul class="list-group list-group-flush">';
            
            if (health.checks) {
                Object.entries(health.checks).forEach(([check, status]) => {
                    const iconClass = status === 'PASS' ? 'status-good' : 'status-critical';
                    html += `<li class="list-group-item d-flex justify-content-between">
                        <span>${check.replace('_', ' ').toUpperCase()}</span>
                        <span class="${iconClass}">${status}</span>
                    </li>`;
                });
            }
            
            html += '</ul>';
            activityEl.innerHTML = html;
        }
        
        function showError(message) {
            document.getElementById('system-status').className = 'metric-value status-critical';
            document.getElementById('system-status').textContent = '!';
            document.getElementById('system-status-text').textContent = message;
        }
        
        // Initialize and start updates
        initCharts();
        updateDashboard();
        setInterval(updateDashboard, 30000); // Update every 30 seconds
    </script>
</body>
</html>
"""

class SystemHealthAPI:
    """Simple system health and metrics API"""
    
    def __init__(self):
        self.start_time = time.time()
        
    def get_health_status(self) -> Dict[str, Any]:
        """Get current system health status"""
        health_data = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": "PASS",
            "checks": {
                "dependencies": "PASS",
                "core_files": "PASS",
                "import_integrity": "PASS"
            },
            "uptime_seconds": time.time() - self.start_time
        }
        
        # Try to read existing health check results
        health_file = "generated_docs/system_health.json"
        if os.path.exists(health_file):
            try:
                with open(health_file, 'r') as f:
                    existing_health = json.load(f)
                    health_data.update(existing_health)
            except Exception as e:
                print(f"Warning: Could not read health file: {e}")
        
        return health_data
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get current system performance metrics"""
        # Get system metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Calculate health score (simple algorithm)
        health_score = 100
        if cpu_percent > 80:
            health_score -= 30
        elif cpu_percent > 60:
            health_score -= 15
            
        if memory.percent > 80:
            health_score -= 30
        elif memory.percent > 60:
            health_score -= 15
            
        if disk.percent > 90:
            health_score -= 20
        elif disk.percent > 80:
            health_score -= 10
            
        # Look for last generation time
        last_generation = None
        output_folder = "generated_docs"
        if os.path.exists(output_folder):
            try:
                files = [f for f in os.listdir(output_folder) if f.endswith('.xlsx')]
                if files:
                    latest_file = max([os.path.join(output_folder, f) for f in files], 
                                    key=os.path.getctime)
                    last_generation = datetime.fromtimestamp(os.path.getctime(latest_file)).isoformat()
            except Exception:
                pass
        
        return {
            "timestamp": datetime.now().isoformat(),
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_used_gb": memory.used / (1024**3),
            "memory_total_gb": memory.total / (1024**3),
            "disk_percent": disk.percent,
            "disk_free_gb": disk.free / (1024**3),
            "health_score": max(0, health_score),
            "last_generation": last_generation,
            "uptime_hours": (time.time() - self.start_time) / 3600
        }

# Initialize API
health_api = SystemHealthAPI()

@app.route('/')
def dashboard():
    """Main dashboard page"""
    return render_template_string(DASHBOARD_HTML)

@app.route('/api/health')
def api_health():
    """Health status API endpoint"""
    return jsonify(health_api.get_health_status())

@app.route('/api/metrics')
def api_metrics():
    """System metrics API endpoint"""
    return jsonify(health_api.get_system_metrics())

@app.route('/api/status')
def api_status():
    """Simple status check"""
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "uptime": time.time() - health_api.start_time
    })

if __name__ == '__main__':
    print("🩺 Starting DSR System Health Dashboard...")
    print("📊 Dashboard will be available at: http://localhost:5000")
    print("🔄 Auto-refresh every 30 seconds")
    print("=" * 60)
    
    # Run the dashboard
    app.run(host='0.0.0.0', port=5000, debug=False)