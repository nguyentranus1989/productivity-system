async function loadSchedulingInsights() {
    const response = await fetch('/api/scheduling/insights');
    const insights = await response.json();
    
    let html = '<div class="insights-container">';
    insights.forEach(day => {
        const icon = day.variance_pct > 20 ? '⚠️' : 
                     day.variance_pct < -20 ? '📉' : '✅';
        const color = day.recommendation === 'Add staff' ? 'red' : 
                      day.recommendation === 'Reduce staff' ? 'orange' : 'green';
        
        html += `
            <div class="day-insight" style="color: ${color}">
                ${icon} ${day.day}: ${day.recommendation}
                (Typically ${Math.abs(day.variance_pct)}% ${day.variance_pct > 0 ? 'busier' : 'slower'})
            </div>`;
    });
    html += '</div>';
    
    document.getElementById('scheduling-insights').innerHTML = html;
}

// Auto-refresh every 5 minutes
setInterval(loadSchedulingInsights, 300000);
loadSchedulingInsights();
