import { useState, useEffect, useRef } from 'react';
import './index.css';
import SpotlightBackground from './SpotlightBackground';

function App() {
  const [stats, setStats] = useState({
    people: 0,
    males: 0,
    females: 0,
    risk_score: 0,
    recent_alerts: []
  });
  
  const [heatmap, setHeatmap] = useState(false);
  const [fps, setFps] = useState(0);
  const framesRef = useRef(0);
  const lastTimeRef = useRef(performance.now());

  // Fetch Stats Polling
  useEffect(() => {
    const fetchStats = async () => {
      try {
        const response = await fetch('http://127.0.0.1:5000/api/stats');
        if (!response.ok) return;
        const data = await response.json();
        
        setStats({
          people: data.people,
          males: data.males,
          females: data.females,
          risk_score: data.risk_score,
          recent_alerts: data.recent_alerts || []
        });
      } catch (error) {
        console.error("Error fetching stats:", error);
      }
    };

    const intervalId = setInterval(fetchStats, 500);
    return () => clearInterval(intervalId);
  }, []);

  // FPS Counter loop
  useEffect(() => {
    let animationFrameId;
    const loop = () => {
      framesRef.current += 1;
      const now = performance.now();
      if (now - lastTimeRef.current >= 1000) {
        setFps(framesRef.current);
        framesRef.current = 0;
        lastTimeRef.current = now;
      }
      animationFrameId = requestAnimationFrame(loop);
    };
    loop();
    return () => cancelAnimationFrame(animationFrameId);
  }, []);

  // Compute risk classes
  const isCritical = stats.risk_score >= 4;
  const isElevated = stats.risk_score > 0;
  let riskText = "SAFE";
  if (isCritical) riskText = "CRITICAL";
  else if (isElevated) riskText = "ELEVATED";

  const getAlertIcon = (type) => {
    switch(type) {
      case 'WEAPON': return 'fa-person-rifle';
      case 'SOS': return 'fa-hand-paper';
      case 'FIGHT': return 'fa-user-ninja';
      case 'SCREAM': return 'fa-volume-high';
      case 'CRIMINAL': return 'fa-user-secret';
      default: return 'fa-exclamation-triangle';
    }
  };

  return (
    <SpotlightBackground>
      <div className="dashboard">
        {/* Sidebar */}
      <aside className="sidebar glass-panel">
        <div className="brand">
          <i className="fa-solid fa-shield-halved"></i>
          Aegis AI
        </div>
        <div className="nav-menu">
          <a className="nav-item active"><i className="fa-solid fa-desktop"></i> Live Monitor</a>
          <a className="nav-item"><i className="fa-solid fa-chart-line"></i> Analytics</a>
          <a className="nav-item"><i className="fa-solid fa-video"></i> Recordings</a>
          <a className="nav-item"><i className="fa-solid fa-users-viewfinder"></i> Face Database</a>
          <a className="nav-item"><i className="fa-solid fa-gear"></i> Settings</a>
        </div>
      </aside>

      {/* Main Content */}
      <main className="main-content">
        <div className="glass-panel" style={{ padding: 0, paddingBottom: '20px' }}>
          <div className="video-container" id="videoContainer">
            <img 
              id="videoFeed" 
              src={`http://127.0.0.1:5000/video_feed${heatmap ? '?heatmap=1' : ''}`} 
              alt="Live Camera Feed" 
            />
            <div className="video-overlay">
              <div className="status-badge status-live">LIVE</div>
              <div className="status-badge" style={{ background: 'rgba(0,0,0,0.5)', color: 'white' }}>FPS: {fps}</div>
            </div>
          </div>
          
          <div className="controls" style={{ padding: '0 20px', marginTop: '15px' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 500 }}>Live Feed Processing</h3>
            <div style={{ display: 'flex', gap: '20px', alignItems: 'center' }}>
              <span style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>Overlay Heatmap</span>
              <label className="toggle-switch">
                <input 
                  type="checkbox" 
                  checked={heatmap} 
                  onChange={(e) => setHeatmap(e.target.checked)} 
                />
                <span className="slider"></span>
              </label>
            </div>
          </div>
        </div>

        <div className="stats-grid">
          <div className="stat-card glass-panel">
            <div className="stat-label">Total People</div>
            <div className="stat-value">{stats.people}</div>
          </div>
          <div className="stat-card glass-panel">
            <div className="stat-label">Females</div>
            <div className="stat-value">{stats.females}</div>
          </div>
          <div className="stat-card glass-panel">
            <div className="stat-label">Males</div>
            <div className="stat-value">{stats.males}</div>
          </div>
          <div className={`stat-card glass-panel ${isElevated ? 'risk-high' : ''} ${isCritical ? 'risk-critical' : ''}`}>
            <div className="stat-label">Risk Level</div>
            <div className="stat-value">{riskText}</div>
          </div>
        </div>
      </main>

      {/* Right Panel */}
      <aside className="right-panel glass-panel">
        <div className="panel-header">
          Incident Alerts
          <span style={{ fontSize: '0.8rem', background: 'rgba(255,51,102,0.2)', color: 'var(--accent-red)', padding: '4px 8px', borderRadius: '12px' }}>Live</span>
        </div>
        <div className="alerts-feed">
          {stats.recent_alerts.map(alert => (
            <div key={alert.id} className={`alert-card ${alert.level === 'high' ? '' : 'warning'}`}>
              <div className="alert-icon">
                <i className={`fa-solid ${getAlertIcon(alert.type)}`}></i>
              </div>
              <div className="alert-details">
                <div className="alert-title">{alert.message}</div>
                <div className="alert-time">{alert.time}</div>
              </div>
            </div>
          ))}
          {stats.recent_alerts.length === 0 && (
             <div style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', textAlign: 'center', marginTop: '20px' }}>
                No recent incidents
             </div>
          )}
        </div>
        </aside>
      </div>
    </SpotlightBackground>
  );
}

export default App;
