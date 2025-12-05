from flask import Flask, render_template_string, jsonify, request, Response
from werkzeug.utils import secure_filename
import os, threading, time, uuid, pandas as pd
from model_utils import *
from ui_templates import *

def allowed_video(filename: str) -> bool:
    return os.path.splitext(filename)[1].lower() in {".mp4", ".mov", ".avi", ".mkv"}

def allowed_json(filename: str) -> bool:
    return os.path.splitext(filename)[1].lower() in {".json"}


app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = os.path.join(os.getcwd(), "uploads")
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
ALLOWED_VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv"}
ALLOWED_JSON_EXTS = {".json"}
JOBS = {}
JOBS_LOCK = threading.Lock()
latest_status = "Initializing..."
camera_active = True
status_lock = threading.Lock()
error_message = ""
EXPERIMENT_RESULTS_DASHBOARD = "dashboard_results.csv"

@app.route("/")
def index():
    return render_template_string(INDEX_HTML, base_css=BASE_CSS, base_nav=BASE_NAV)

@app.route("/dashboard")
def dashboard():
    return render_template_string(DASHBOARD_HTML, base_css=BASE_CSS, base_nav=BASE_NAV)

@app.route("/dashboard/data")
def dashboard_data():
    try:
        import os
        print("Dashboard data route called!")
        if not os.path.exists(EXPERIMENT_RESULTS_DASHBOARD):
            print("CSV file does not exist!")
            return jsonify({"error": "No exported dashboard data found."}), 404
        df = pd.read_csv(EXPERIMENT_RESULTS_DASHBOARD)
        print("Loaded CSV, columns:", df.columns)
        print(df.head())

        # Defensive: Ensure columns exist
        needed = ["video", "macroF1", "macroP", "macroR", "microF1", "microP", "microR", "overall_acc",
                  "best_class", "best_f1", "worst_class", "worst_f1"]
        for col in needed:
            if col not in df:
                print(f"Column {col} not present, creating!")
                df[col] = 0 if 'class' not in col else ""
        df.fillna(0, inplace=True)

        # Add DistanceGroup
        def categorize(video):
            video = str(video).lower()
            if 'near' in video: return 'Near'
            if 'medium' in video: return 'Medium'
            if 'far' in video: return 'Far'
            return 'Other'
        df['DistanceGroup'] = df['video'].apply(categorize)
        base_df = df[df['video'] != 'AVERAGE']
        group_stats = base_df.groupby('DistanceGroup')[["macroF1","microF1","overall_acc"]].mean().to_dict()
        all_stats = base_df[["macroF1","microF1","overall_acc"]].mean().to_dict()
        group_stats["All"] = all_stats
        return jsonify({
            "columns": list(df.columns),
            "data": df.to_dict(orient='records'),
            "group_stats": group_stats
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500




@app.route("/experimentation")
def experimentation():
    return render_template_string(EXPERIMENTATION_HTML, base_css=BASE_CSS, base_nav=BASE_NAV)

@app.route("/experimentation/start", methods=["POST"])
def experimentation_start():
    try:
        vids = request.files.getlist("videos")
        gts  = request.files.getlist("gts")
        video_paths = []
        for f in vids:
            if not f.filename: continue
            if not allowed_video(f.filename):
                return jsonify({"ok": False, "error": f"Unsupported video: {f.filename}"}), 400
            fn = secure_filename(f.filename)
            out_path = os.path.join(app.config["UPLOAD_FOLDER"], fn)
            f.save(out_path)
            video_paths.append(out_path)
        gt_paths = {}
        for g in gts:
            if not g.filename: continue
            if not allowed_json(g.filename):
                return jsonify({"ok": False, "error": f"Unsupported GT: {g.filename}"}), 400
            fn = secure_filename(g.filename)
            out_path = os.path.join(app.config["UPLOAD_FOLDER"], fn)
            g.save(out_path)
            base = os.path.splitext(fn)[0]
            gt_paths[base] = out_path
        if not video_paths:
            return jsonify({"ok": False, "error": "No valid videos uploaded."}), 400
        job_id = str(uuid.uuid4())
        with JOBS_LOCK:
            JOBS[job_id] = {"status":"queued","total_frames":0,"done_frames":0,"eta":None,"started_at":None,"error":None,"result_html":""}
        th = threading.Thread(target=_process_videos_job, args=(job_id, video_paths, gt_paths), daemon=True)
        th.start()
        return jsonify({"ok": True, "job_id": job_id})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/experimentation/status", methods=["GET"])
def experimentation_status():
    job_id = request.args.get("job")
    if not job_id: return jsonify({"ok": False, "error": "Missing job id"}), 400
    with JOBS_LOCK:
        if job_id not in JOBS:
            return jsonify({"ok": False, "error": "Unknown job id"}), 404
        return jsonify({"ok": True, **JOBS[job_id]})

@app.route("/experimentation/result", methods=["GET"])
def experimentation_result():
    job_id = request.args.get("job")
    if not job_id: return "Missing job id", 400
    with JOBS_LOCK:
        if job_id not in JOBS: return "Unknown job id", 404
        html = JOBS[job_id].get("result_html","")
    return f"{BASE_CSS}<div class='page-wrap'>{html}</div>"

def _process_videos_job(job_id: str, video_paths: list, gt_paths_by_base: dict):
    start = time.time()
    try:
        eff = 10.0
        totals = []
        summary_rows = []
        result_blocks = []
        for vp in video_paths:
            cap = cv2.VideoCapture(vp)
            tf_raw = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            cap.release()
            step = max(1, int(round(src_fps / eff)))
            if tf_raw > 0:
                tf_proc = math.ceil(tf_raw / step)
            else:
                tf_proc = int(eff * 60)
            totals.append(tf_proc)
        total_frames = int(sum(totals))
        with JOBS_LOCK:
            JOBS[job_id].update({"status":"running","total_frames":total_frames,"done_frames":0,"eta":None,"started_at":start})
        done_frames = 0
        def on_frame():
            nonlocal done_frames, start, total_frames
            done_frames += 1
            now = time.time()
            elapsed = max(1e-6, now - start)
            rate = done_frames / elapsed
            remaining = max(0, total_frames - done_frames)
            eta = remaining / rate if rate > 0 else None
            with JOBS_LOCK:
                JOBS[job_id]["done_frames"] = int(done_frames)
                JOBS[job_id]["eta"] = float(eta) if eta is not None else None
        for vp in video_paths:
            base_name = os.path.basename(vp)
            base = os.path.splitext(base_name)[0]
            res = analyze_video_time_matrix(
                vp, conf_thresh=0.25, on_frame=on_frame,
                return_frame_matrix=True, eff_fps=eff
            )
            sec_df = pd.DataFrame({
                "class": CLASSES,
                "seconds": [round(res["seconds"][c], 2) for c in CLASSES]
            })
            html_block = f'<div class="upload-card">'
            html_block += f'<h3 style="margin-top:0;">{base_name} — Seconds per class @ 10 FPS</h3>'
            html_block += f'<p class="note">Each row is a class; value is total seconds detection at 10 FPS.</p>'
            html_block += sec_df.to_html(index=False)
            html_block += '</div>'
            if base in gt_paths_by_base and res["frame_matrix"] is not None:
                gt_path = gt_paths_by_base[base]
                _, gt_by_class = load_gt_json(gt_path)
                prM = res["frame_matrix"]
                class_list = res["frame_classes"]
                gtM = gt_to_frame_matrix(gt_by_class, res["fps"], res["duration_sec"], class_list)
                n = min(prM.shape[0], gtM.shape[0])
                prM = prM[:n, :]
                gtM = gtM[:n, :]
                perclass, macroP, macroR, macroF1, microP, microR, microF1, overall_acc = per_class_prf_from_mats(gtM, prM, class_list)
                keep_rows = []
                for i, x in enumerate(perclass):
                    if x["support_frames"] > 0 or prM[:,i].sum() > 0:
                        keep_rows.append(x)
                if not keep_rows:
                    keep_rows = perclass
                mdf = pd.DataFrame(keep_rows)[["class","precision","recall","f1","support_frames"]]
                mdf[["precision","recall","f1"]] = (mdf[["precision","recall","f1"]]*100).round(2)
                html_block += '<div class="upload-card">'
                html_block += f'<h3>Metrics for {base_name} @ 10 FPS</h3>'
                html_block += '<p class="note">Per-class frame-wise precision / recall / F1 (multi-label; only classes present in GT or predicted).</p>'
                html_block += mdf.to_html(index=False)
                html_block += (
                    f'<p class="note"><b>Macro</b> P/R/F1: {np.mean([x["precision"] for x in keep_rows])*100:.2f}% / '
                    f'{np.mean([x["recall"] for x in keep_rows])*100:.2f}% / '
                    f'{np.mean([x["f1"] for x in keep_rows])*100:.2f}%'
                    f' &nbsp; | &nbsp; <b>Micro</b> P/R/F1: {microP*100:.2f}% / {microR*100:.2f}% / {microF1*100:.2f}%'
                    f' &nbsp; | &nbsp; <b>Overall accuracy</b>: {overall_acc*100:.2f}%</p>'
                )
                html_block += '</div>'
                summary_rows.append({
                    "video": base_name,
                    "macroF1": np.mean([x["f1"] for x in keep_rows])*100 if keep_rows else 0,
                    "macroP": np.mean([x["precision"] for x in keep_rows])*100 if keep_rows else 0,
                    "macroR": np.mean([x["recall"] for x in keep_rows])*100 if keep_rows else 0,
                    "microF1": microF1 * 100,
                    "microP": microP * 100,
                    "microR": microR * 100,
                    "overall_acc": overall_acc * 100,
                    "best_class": max(keep_rows, key=lambda x: x["f1"])["class"] if keep_rows else "n/a",
                    "best_f1": max([x["f1"] for x in keep_rows])*100 if keep_rows else 0,
                    "worst_class": min(keep_rows, key=lambda x: x["f1"])["class"] if keep_rows else "n/a",
                    "worst_f1": min([x["f1"] for x in keep_rows])*100 if keep_rows else 0,
                })
            result_blocks.append(html_block)
        if summary_rows:
            df = pd.DataFrame(summary_rows)
            numeric_cols = [
                "macroF1","macroP","macroR",
                "microF1","microP","microR","overall_acc","best_f1","worst_f1"
            ]
            avg_row = {col: df[col].mean() for col in numeric_cols}
            avg_row["video"] = "AVERAGE"
            avg_row["best_class"] = df["best_class"].mode().iloc[0] if not df["best_class"].mode().empty else "n/a"
            avg_row["worst_class"] = df["worst_class"].mode().iloc[0] if not df["worst_class"].mode().empty else "n/a"
            df = pd.concat([df, pd.DataFrame([avg_row])], ignore_index=True)
            summary_html = (
                '<div class="upload-card">'
                '<h3 style="margin-top:0;">Summary of Accuracy and Metrics (all scored videos)</h3>'
                '<p class="note">Final row is experiment-wide average. "Best/Worst class" is most frequent best/worst (by F1) among relevant classes per video. All metrics in %.</p>'
                + df[[
                    "video","macroF1","macroP","macroR",
                    "microF1","microP","microR",
                    "overall_acc","best_class","best_f1","worst_class","worst_f1"
                ]].round(2).to_html(index=False)
                + '</div>'
            )
            result_blocks.insert(0, summary_html)
        with JOBS_LOCK:
            JOBS[job_id]["status"] = "done"
            JOBS[job_id]["result_html"] = "\n".join(result_blocks)
            JOBS[job_id]["summary_rows"] = summary_rows
    except Exception as e:
        with JOBS_LOCK:
            JOBS[job_id]["status"] = "error"
            JOBS[job_id]["error"] = str(e)

@app.route("/experimentation/dashboard_export", methods=["POST"])
def dashboard_export():
    try:
        with JOBS_LOCK:
            # Find most recent job with summary rows
            jobs = [j for j in JOBS.values() if j.get("status") == "done" and j.get("summary_rows")]
            if not jobs:
                return jsonify({"ok": False, "error": "No experiment results available. Run processing first!"})
            summary_rows = jobs[-1]["summary_rows"]
        if not summary_rows:
            return jsonify({"ok": False, "error": "No summary rows found in last job!"})
        df = pd.DataFrame(summary_rows)
        df.to_csv(EXPERIMENT_RESULTS_DASHBOARD, index=False)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@app.route("/video_feed")
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route("/get_status")
def get_status():
    with status_lock:
        return jsonify({"latest_status": latest_status, "camera_active": camera_active, "error_message": error_message})

def generate_frames():
    global latest_status, camera_active, error_message
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        camera_active = False
        error_message = "Unable to access webcam."
        return
    camera_active = True
    last_state = None
    prev = time.time()
    ema_fps = 0.0
    alpha = 0.1
    while True:
        success, frame = cap.read()
        if not success:
            camera_active = False
            error_message = "Camera disconnected."
            break
        results = model(frame)
        annotated_frame = results[0].plot()
        detected_labels = names_from_result(results[0])
        now = time.time()
        inst_fps = 1.0 / max(1e-6, (now - prev))
        prev = now
        ema_fps = (1 - alpha) * ema_fps + alpha * inst_fps if ema_fps > 0 else inst_fps
        cv2.putText(
            annotated_frame,
            f"FPS: {ema_fps:.1f}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (0, 255, 0),
            2,
            cv2.LINE_AA
        )
        current_state = "🟡 No Person / Other Headwear"
        if any("helmet missing" in lbl for lbl in detected_labels):
            current_state = "⚠ No Helmet Detected – Please wear your helmet"
        elif any("helmet false" in lbl for lbl in detected_labels):
            current_state = "❌ Helmet False – Please wear a real helmet"
        elif any("helmet not secure" in lbl for lbl in detected_labels):
            current_state = "⚠ Helmet Not Secure – Please fasten your strap properly"
        elif any("helmet poor fit" in lbl for lbl in detected_labels):
            current_state = "⚠ Poor Fit – Adjust your helmet to fit properly"
        elif any("helmet bad clip" in lbl for lbl in detected_labels):
            current_state = "⚠ Bad Clip – Please fasten your helmet clip securely"
        elif any(("helmet front" in lbl) or ("helmet back" in lbl) for lbl in detected_labels):
            current_state = "📸 Tilt your head sideways – Show helmet strap/clip"
        elif any("helmet on head" in lbl for lbl in detected_labels):
            current_state = "✅ Helmet On"
        if current_state != last_state:
            with status_lock:
                latest_status = current_state
            last_state = current_state
        ret, buffer = cv2.imencode('.jpg', annotated_frame)
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        time.sleep(0.03)
    cap.release()
