document.addEventListener('DOMContentLoaded', () => {
    const statPeople = document.getElementById('statPeople');
    const statFemales = document.getElementById('statFemales');
    const statMales = document.getElementById('statMales');
    const statRisk = document.getElementById('statRisk');
    const riskCard = document.getElementById('riskCard');
    const alertsFeed = document.getElementById('alertsFeed');
    const heatmapToggle = document.getElementById('heatmapToggle');
    const videoFeed = document.getElementById('videoFeed');

    let processedAlertIds = new Set();

    // Toggle heatmap mode by updating image source
    heatmapToggle.addEventListener('change', (e) => {
        const isHeatmap = e.target.checked;
        if (isHeatmap) {
            videoFeed.src = "/video_feed?heatmap=1";
        } else {
            videoFeed.src = "/video_feed";
        }
    });

    function createAlertCard(alert) {
        // alert = {id: string, type: string, message: string, time: string, level: string}
        const card = document.createElement('div');
        card.className = `alert-card ${alert.level === 'high' ? '' : 'warning'}`;
        
        let iconClass = 'fa-exclamation-triangle';
        if (alert.type === 'WEAPON') iconClass = 'fa-person-rifle';
        if (alert.type === 'SOS') iconClass = 'fa-hand-paper';
        if (alert.type === 'FIGHT') iconClass = 'fa-user-ninja';
        if (alert.type === 'SCREAM') iconClass = 'fa-volume-high';
        if (alert.type === 'CRIMINAL') iconClass = 'fa-user-secret';

        card.innerHTML = `
            <div class="alert-icon">
                <i class="fa-solid ${iconClass}"></i>
            </div>
            <div class="alert-details">
                <div class="alert-title">${alert.message}</div>
                <div class="alert-time">${alert.time}</div>
            </div>
        `;
        return card;
    }

    async function fetchStats() {
        try {
            const response = await fetch('/api/stats');
            const data = await response.json();

            // Update stats
            statPeople.innerText = data.people;
            statFemales.innerText = data.females;
            statMales.innerText = data.males;

            // Update Risk Score
            if (data.risk_score >= 4) {
                statRisk.innerText = "CRITICAL";
                riskCard.classList.add('risk-critical');
                riskCard.classList.add('risk-high');
            } else if (data.risk_score > 0) {
                statRisk.innerText = "ELEVATED";
                riskCard.classList.remove('risk-critical');
                riskCard.classList.add('risk-high');
            } else {
                statRisk.innerText = "SAFE";
                riskCard.classList.remove('risk-critical');
                riskCard.classList.remove('risk-high');
            }

            // Update Alerts Feed
            if (data.recent_alerts && data.recent_alerts.length > 0) {
                data.recent_alerts.forEach(alert => {
                    if (!processedAlertIds.has(alert.id)) {
                        processedAlertIds.add(alert.id);
                        const alertElement = createAlertCard(alert);
                        alertsFeed.prepend(alertElement);
                        
                        // Keep only last 20 alerts in DOM
                        if (alertsFeed.children.length > 20) {
                            alertsFeed.removeChild(alertsFeed.lastChild);
                        }
                    }
                });
            }
        } catch (error) {
            console.error("Error fetching stats:", error);
        }
    }

    // Fetch stats every 500ms
    setInterval(fetchStats, 500);

    // Simple FPS counter
    let frames = 0;
    let lastTime = performance.now();
    const fpsCounter = document.getElementById('fpsCounter');

    function loop() {
        frames++;
        const now = performance.now();
        if (now - lastTime >= 1000) {
            fpsCounter.innerText = `FPS: ${frames}`;
            frames = 0;
            lastTime = now;
        }
        requestAnimationFrame(loop);
    }
    requestAnimationFrame(loop);
});
