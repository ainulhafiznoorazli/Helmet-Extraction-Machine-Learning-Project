BASE_NAV = """
<nav>
  <h1>Helmet Detection</h1>
  <div>
    <a href="/">Live Stream</a>
    <a href="/dashboard">Dashboard</a>
    <a href="/experimentation">Experimentation</a>
  </div>
</nav>
"""

BASE_CSS = """
<style>
  body { margin:0; font-family:'Segoe UI',sans-serif; background:#0d1117; color:#e6edf3; }
  nav { background:#161b22; padding:15px 30px; display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #30363d; }
  nav h1 { color:#58a6ff; margin:0; font-size:1.5rem; }
  nav a { color:#c9d1d9; text-decoration:none; margin-left:20px; font-weight:500; }
  nav a:hover { color:#58a6ff; }
  .container { display:flex; justify-content:center; margin-top:30px; gap:40px; }
  .video-box { border:3px solid #238636; border-radius:12px; overflow:hidden; box-shadow:0 0 20px rgba(35,134,54,.3); }
  .info-panel { background:#161b22; border-radius:10px; padding:20px; width:320px; height:420px; box-shadow:0 0 15px rgba(0,0,0,.3); display:flex; flex-direction:column; }
  .status-header { display:flex; align-items:center; justify-content:space-between; margin-bottom:10px; }
  .status-indicator { width:15px; height:15px; border-radius:50%; background:gray; }
  .status-box { border:2px solid #30363d; border-radius:8px; background:#0d1117; color:#e6edf3; padding:10px; height:300px; overflow-y:auto; font-size:1rem; }
  .error-message { color:#f85149; text-align:center; margin-top:10px; font-weight:bold; }
  footer { margin-top:30px; text-align:center; color:#8b949e; font-size:.9rem; }
  .page-wrap { padding: 20px 30px; }
  .upload-card { background:#161b22; border:1px solid #30363d; border-radius:12px; padding:18px; margin:20px 0; }
  .btn { background:#238636; border:none; color:#fff; padding:10px 14px; border-radius:8px; cursor:pointer; font-weight:600; }
  .btn:hover { filter:brightness(.95); }
  .note { color:#8b949e; font-size:.9rem; }
  table.dataframe { border-collapse:collapse; width:100%; margin-top:10px; background:#0d1117; color:#e6edf3; }
  table.dataframe th, table.dataframe td { border:1px solid #30363d; padding:8px; text-align:right; }
  table.dataframe th { background:#161b22; text-align:center; }
  .grid { display:grid; grid-template-columns:1fr; gap:24px; }
  .progresswrap { margin-top:16px; }
  .barouter { width:100%; height:16px; background:#30363d; border-radius:8px; overflow:hidden; }
  .barinner { height:100%; width:0%; background:#238636; transition:width .25s; }
  .eta { color:#8b949e; margin-top:6px; }
  .hidden { display:none; }
</style>
"""

INDEX_HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>Helmet Detection Dashboard</title>
  {{ base_css | safe }}
  <script>
    function updateStatus(){
      fetch('/get_status').then(r=>r.json()).then(data=>{
        const box = document.getElementById('status_box');
        const indicator = document.getElementById('cam_status');
        const errMsg = document.getElementById('error_msg');
        indicator.style.backgroundColor = data.camera_active ? "#2ea043" : "#f85149";
        errMsg.innerText = data.error_message || "";
        const lines = box.innerHTML.split('<br>');
        const last = lines.length ? lines[lines.length-2] : "";
        if(last !== data.latest_status){
          box.innerHTML += data.latest_status + "<br>";
          box.scrollTop = box.scrollHeight;
        }
      });
    }
    setInterval(updateStatus,1000);
  </script>
</head>
<body>
  {{ base_nav | safe }}
  <div class="container">
    <div class="video-box"><img src="/video_feed" width="720"></div>
    <div class="info-panel">
      <div class="status-header"><h2 style="color:#58a6ff;">Detection Log</h2><div class="status-indicator" id="cam_status"></div></div>
      <div class="status-box" id="status_box">Initializing...<br></div>
      <div class="error-message" id="error_msg"></div>
    </div>
  </div>
  <footer>© 2025 Helmet Detection System | YOLOv8 + Flask</footer>
</body>
</html>
"""

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>Helmet Detection Dashboard</title>
  {{ base_css | safe }}
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
  {{ base_nav | safe }}
  <div class="page-wrap">
    <div class="upload-card" style="position:relative;">
      <h2 style="margin:0 0 10px 0;">Experiment Dashboard</h2>
      <div style="position:absolute;top:14px;right:36px;">
         <button class="btn" onclick="refreshDashboard()">Refresh</button>
      </div>
      <select id="distanceGroupSelect" class="btn" style="margin-bottom:12px;">
        <option value="All">All</option>
        <option value="Near">Near</option>
        <option value="Medium">Medium</option>
        <option value="Far">Far</option>
      </select>
      <div id="miniSummaryCards" style="display:flex; gap:20px; margin-bottom:20px;"></div>
      <div id="dashboardSummary"></div>
      <div>
        <canvas id="macroF1Chart" height="140"></canvas>
        <canvas id="classF1Chart" height="180" style="margin-top:34px;"></canvas>
        <canvas id="classFreqChart" height="130" style="margin-top:34px;"></canvas>
      </div>
      <div id="dashboardTable" style="overflow-x:auto;margin-top:32px;"></div>
    </div>
  </div>
<script>
let dashboardCache = null;
let macroF1Chart=null, classF1Chart=null, classFreqChart=null;
function groupStatsTable(stats, label) {
    let html = `<h3>Average Metrics (${label})</h3>`;
    html += "<table class='dataframe'><thead><tr>";
    html += "<th>Macro F1</th><th>Micro F1</th><th>Overall Acc</th>";
    html += "</tr></thead><tbody><tr>";
    html += `<td>${(stats.macroF1||0).toFixed(2)}</td>`;
    html += `<td>${(stats.microF1||0).toFixed(2)}</td>`;
    html += `<td>${(stats.overall_acc||0).toFixed(2)}</td>`;
    html += "</tr></tbody></table>";
    return html;
}
function tableFromDf(js, selectedGroup) {
    let filtered = (selectedGroup==='All') ? js.data : js.data.filter(r => (r.DistanceGroup||'').toLowerCase() === selectedGroup.toLowerCase());
    let showCols = ["video","DistanceGroup","macroF1","microF1","overall_acc","best_class","best_f1","worst_class","worst_f1"];
    let html = "<table class='dataframe'><thead><tr>";
    for(let key of showCols) html += `<th>${key.replace("_", " ")}</th>`;
    html += "</tr></thead><tbody>";
    for(let row of filtered) {
        html += '<tr>';
        for(let key of showCols) html += `<td>${row[key] !== undefined ? row[key] : '-'}</td>`;
        html += '</tr>';
    }
    html += "</tbody></table>";
    return html;
}
function plotMacroF1Chart(js) {
    let groups = ["Near", "Medium", "Far"];
    let vals = groups.map(g => ((js.group_stats[g]||{}).macroF1)||0);
    let ctx = document.getElementById('macroF1Chart').getContext('2d');
    if(macroF1Chart) macroF1Chart.destroy();
    macroF1Chart = new Chart(ctx, {
      type: 'bar',
      data: {labels: groups, datasets:[{label: 'Macro F1', backgroundColor:'#2376c7', data:vals}]},
      options: {responsive:true, plugins:{ legend:{display:false} }, scales:{y:{min:0,max:100}} }
    });
}
function plotClassF1Chart(js, group){
    let filtered = (group==='All')?js.data:js.data.filter(r=>(r.DistanceGroup||'').toLowerCase()===group.toLowerCase());
    let byClass = {};
    filtered.forEach(r=>{
        let c = (r.best_class||"").trim();
        if(!byClass[c]) byClass[c]=[]; 
        byClass[c].push((parseFloat(r.best_f1)||0));
    });
    let sortedKeys = Object.keys(byClass).sort();
    let vals = sortedKeys.map(k=>(byClass[k].reduce((a,b)=>a+b,0)/byClass[k].length)||0);
    let ctx = document.getElementById('classF1Chart').getContext('2d');
    if(classF1Chart) classF1Chart.destroy();
    classF1Chart = new Chart(ctx, {
      type: 'bar',
      data: {labels: sortedKeys, datasets:[{label:'Avg. Best F1 by Class',backgroundColor:'#5beb7d',data:vals}]},
      options:{responsive:true, plugins:{legend:{display:false}},scales:{y:{min:0,max:100}}}
    });
}
function plotClassFreqChart(js, group){
    let filtered = (group==='All')?js.data:js.data.filter(r=>(r.DistanceGroup||'').toLowerCase()===group.toLowerCase());
    let freqBest = {}, freqWorst = {};
    filtered.forEach(r=>{
        let b = (r.best_class||"").trim();
        let w = (r.worst_class||"").trim();
        if (b) freqBest[b] = (freqBest[b]||0) + 1;
        if (w) freqWorst[w] = (freqWorst[w]||0) + 1;
    });
    let unionKeys = Array.from(new Set(Object.keys(freqBest).concat(Object.keys(freqWorst)))).sort();
    let bestVals = unionKeys.map(k=>freqBest[k]||0);
    let worstVals = unionKeys.map(k=>freqWorst[k]||0);
    let ctx = document.getElementById('classFreqChart').getContext('2d');
    if(classFreqChart) classFreqChart.destroy();
    classFreqChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: unionKeys,
        datasets:[
          {label:'Best Class Freq', backgroundColor:'#1660b7', data: bestVals},
          {label:'Worst Class Freq', backgroundColor:'#ee6666', data: worstVals}
        ]
      },
      options:{responsive:true, plugins:{legend:{display:true}},scales:{y:{beginAtZero:true}}}
    });
}
function miniCards(js, group){
  let filtered = (group==='All')?js.data:js.data.filter(r=>(r.DistanceGroup||'').toLowerCase()===group.toLowerCase());
  let bestF1 = Math.max(...filtered.map(r=>parseFloat(r.best_f1)||0));
  let worstF1 = Math.min(...filtered.map(r=>parseFloat(r.worst_f1)||100));
  let bestAcc = Math.max(...filtered.map(r=>parseFloat(r.overall_acc)||0));
  let bestClass = filtered[filtered.findIndex(r=>(r.best_f1==(bestF1+"")))]?.best_class;
  let worstClass = filtered[filtered.findIndex(r=>(r.worst_f1==(worstF1+"")))]?.worst_class;
  return `<div style="background:#161b22;border-left:4px solid #159634;padding:8px 20px;border-radius:9px;"><b>Best F1:</b> ${bestF1.toFixed(2)} (${bestClass})</div>
          <div style="background:#161b22;border-left:4px solid #c04918;padding:8px 20px;border-radius:9px;"><b>Worst F1:</b> ${worstF1.toFixed(2)} (${worstClass})</div>
          <div style="background:#161b22;border-left:4px solid #1a49a6;padding:8px 20px;border-radius:9px;"><b>Best Acc:</b> ${bestAcc.toFixed(2)}%</div>`;
}
function refreshDashboard(selectedGroup="All") {
    fetch('/dashboard/data')
    .then(r=>r.json())
    .then(js=>{
        dashboardCache = js;
        let groupStats = js.group_stats||{};
        let displayStats = selectedGroup==="All" ? groupStats.All : groupStats[selectedGroup];
        if (!displayStats) displayStats = {macroF1:0, microF1:0, overall_acc:0};
        document.getElementById('miniSummaryCards').innerHTML = miniCards(js, selectedGroup);
        document.getElementById('dashboardSummary').innerHTML = groupStatsTable(displayStats, selectedGroup);
        document.getElementById('dashboardTable').innerHTML = tableFromDf(js, selectedGroup);
        plotMacroF1Chart(js);
        plotClassF1Chart(js, selectedGroup);
        plotClassFreqChart(js, selectedGroup);
    });
}
window.onload = function() {
    refreshDashboard();
    document.getElementById('distanceGroupSelect').onchange = function() {
        let val = document.getElementById('distanceGroupSelect').value;
        refreshDashboard(val);
    };
};
</script>
</body>
</html>
"""


EXPERIMENTATION_HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>Experimentation | Helmet Detection</title>
  {{ base_css | safe }}
  <style>
    #exportDashboardBtn {
      position: absolute; right: 40px; top: 30px; z-index: 10;
    }
    #exportNotification {
      position: fixed;
      top: 10px; right: 25px;
      color: #fff; background: #2ea043; padding:10px 18px;
      border-radius:7px; font-weight:600; display:none; z-index:9999;
      box-shadow:0 2px 6px rgba(20,50,20,0.2);
    }
    #exportNotification.error { background:#f85149;}
  </style>
</head>
<body>
  {{ base_nav | safe }}
  <div class="page-wrap" style="position:relative;">
    <button class="btn" id="exportDashboardBtn">Export Results to Dashboard</button>
    <div id="exportNotification"></div>
    <div class="upload-card">
      <h2 style="color:#58a6ff; margin:0 0 10px 0;">Experimentation</h2>
      <p class="note">Upload videos (.mp4, ...). Optional: matching GT JSON for metrics (name must match video, eg: <code>video_01.mp4</code> and <code>video_01.json</code>).</p>
      <form id="expForm">
        <label>Videos:</label><br>
        <input type="file" name="videos" id="videos" accept=".mp4,.mov,.avi,.mkv" multiple><br><br>
        <label>GT JSON (optional):</label><br>
        <input type="file" name="gts" id="gts" accept=".json" multiple><br><br>
        <button class="btn" type="submit">Process</button>
      </form>
      <div id="progress" class="progresswrap hidden">
        <div class="barouter"><div id="bar" class="barinner"></div></div>
        <div class="eta" id="eta">Preparing...</div>
      </div>
      <p class="error-message" id="err"></p>
    </div>
    <div id="results"></div>
  </div>
<script>
  function showExportNote(txt, isSuccess){
    const n = document.getElementById('exportNotification');
    n.className = isSuccess?"":"error";
    n.textContent = txt;
    n.style.display = "block";
    setTimeout(()=>{ n.style.display="none"; }, 2400);
  }
  const form = document.getElementById('expForm');
  const err = document.getElementById('err');
  const progress = document.getElementById('progress');
  const bar = document.getElementById('bar');
  const eta = document.getElementById('eta');
  const results = document.getElementById('results');
  let pollHandle=null;
  function fmtTime(s){
    if(s==null) return '';
    s=Math.max(0,Math.round(s));
    const m=Math.floor(s/60), r=s%60;
    return (m>0? (m+"m "):"") + r + "s remaining";
  }
  form.addEventListener('submit', async (e)=>{
    e.preventDefault();
    err.textContent=""; results.innerHTML="";
    const vfs=document.getElementById('videos').files;
    const gfs=document.getElementById('gts').files;
    if(!vfs || !vfs.length){ err.textContent="Please select at least one video."; return; }
    const fd=new FormData();
    for(let i=0;i<vfs.length;i++) fd.append('videos', vfs[i]);
    for(let i=0;i<gfs.length;i++) fd.append('gts', gfs[i]);
    progress.classList.remove('hidden'); bar.style.width='0%'; eta.textContent='Uploading...';
    const r=await fetch('/experimentation/start',{method:'POST', body:fd});
    const js=await r.json();
    if(!js.ok){ err.textContent=js.error||'Failed to start job.'; progress.classList.add('hidden'); return; }
    const job=js.job_id;
    async function poll(){
      const res=await fetch('/experimentation/status?job='+job);
      const st=await res.json();
      if(!st.ok){ err.textContent=st.error||'Status error.'; clearInterval(pollHandle); return; }
      const tot=st.total_frames||0, done=st.done_frames||0;
      const pct = tot>0 ? Math.min(100, Math.round((done/tot)*100)) : 0;
      bar.style.width=pct+'%';
      eta.textContent=(st.status==='done')?'Finalizing...':(st.status==='running')?(pct+'% • '+(fmtTime(st.eta)||'Estimating...')):st.status;
      if(st.status==='done'){
        clearInterval(pollHandle);
        const rr=await fetch('/experimentation/result?job='+job);
        const html=await rr.text();
        results.innerHTML=html;
        progress.classList.add('hidden');
      }else if(st.status==='error'){
        clearInterval(pollHandle);
        err.textContent=st.error||'Processing error.';
        progress.classList.add('hidden');
      }
    }
    pollHandle=setInterval(poll,500); poll();
  });
  document.getElementById('exportDashboardBtn').onclick = async function() {
      const r = await fetch('/experimentation/dashboard_export', {method:'POST'});
      const js = await r.json();
      if(js.ok) showExportNote("Data exported! View summary in Dashboard tab.",true);
      else showExportNote("Export failed: " + (js.error || ""),false);
  };
</script>
</body>
</html>
"""
