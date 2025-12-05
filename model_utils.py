import cv2, math, numpy as np, json
from ultralytics import YOLO

MODEL_PATH = r"C:\Users\zacha\runs\detect\train21\weights\best.pt" #train21 for og best.pt
CLASSES = [
    "helmet back", "helmet bad clip", "helmet false", "helmet front",
    "helmet not secure", "helmet on head", "helmet poor fit",
    "helmet missing", "null"
]
model = YOLO(MODEL_PATH)

def names_from_result(result):
    if result.boxes is None or len(result.boxes) == 0:
        return []
    out = []
    for b in result.boxes:
        cls_id = int(b.cls[0])
        name = model.names.get(cls_id, str(cls_id)).lower()
        out.append(name)
    return out

def normalize_label(lbl):
    l = lbl.lower().strip()
    # Unify all helmet-missing classes:
    if "no helmet" in l or "bare" in l or l == "no" or "other headwear" in l or "cap" in l or "hood" in l:
        return "helmet missing"
    if "helmet false" in l:
        return "helmet false"
    if "helmet not secure" in l or "not secure" in l:
        return "helmet not secure"
    if "helmet poor fit" in l or "poor fit" in l:
        return "helmet poor fit"
    if "helmet bad clip" in l or "bad clip" in l:
        return "helmet bad clip"
    if "helmet front" in l:
        return "helmet front"
    if "helmet back" in l:
        return "helmet back"
    if "helmet on head" in l or l == "helmet on":
        return "helmet on head"
    if l == "helmet missing":
        return l
    for c in CLASSES:
        if c == l:
            return c
    return ""

def analyze_video_time_matrix(video_path, conf_thresh=0.25, on_frame=None, return_frame_matrix=False, eff_fps=10.0):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_step = max(1, int(round(src_fps / eff_fps)))
    sec_per_class = {c: 0.0 for c in CLASSES}
    real_classes = [c for c in CLASSES if c != "null"]
    frame_rows = []
    raw_idx = 0
    proc_idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if (raw_idx % frame_step) != 0:
            raw_idx += 1
            continue
        results = model.predict(frame, conf=conf_thresh, verbose=False)
        result = results[0]
        raw_labels = names_from_result(result)
        present = set()
        for lbl in raw_labels:
            norm = normalize_label(lbl)
            if norm and norm in real_classes:
                present.add(norm)
        dt = 1.0 / eff_fps
        if present:
            for c in present:
                sec_per_class[c] += dt
            if return_frame_matrix:
                vec = np.zeros(len(real_classes), dtype=bool)
                for ci, cname in enumerate(real_classes):
                    if cname in present:
                        vec[ci] = True
                frame_rows.append(vec)
        else:
            sec_per_class["null"] += dt
            if return_frame_matrix:
                frame_rows.append(np.zeros(len(real_classes), dtype=bool))
        proc_idx += 1
        raw_idx += 1
        if on_frame:
            on_frame()
    cap.release()
    duration_sec = proc_idx / eff_fps if eff_fps > 0 else 0.0
    pct_per_class = {
        c: ((sec_per_class[c] / duration_sec) * 100.0) if duration_sec > 0 else 0.0
        for c in CLASSES
    }
    frame_matrix = np.vstack(frame_rows) if (return_frame_matrix and frame_rows) else None
    return {
        "video_path": video_path,
        "fps": eff_fps,
        "duration_sec": duration_sec,
        "seconds": sec_per_class,
        "percent": pct_per_class,
        "total_frames": proc_idx,
        "frame_matrix": frame_matrix,
        "frame_classes": real_classes
    }

def load_gt_json(gt_path):
    with open(gt_path, "r", encoding="utf-8") as f:
        d = json.load(f)
    if not isinstance(d, dict):
        raise ValueError(f"GT JSON is not a dict: {gt_path}")
    fps = float(d.get("fps", 30.0))
    tracks = d.get("tracks", {})
    out_by_class = {}
    for tid, arr in tracks.items():
        for it in arr:
            klass = it["class"].lower().strip()
            if klass in ["no helmet", "other headwear", "bare", "cap", "hood"]:
                klass = "helmet missing"
            out_by_class.setdefault(klass, []).append((float(it["t0"]), float(it["t1"])))
    return fps, out_by_class

def gt_to_frame_matrix(gt_by_class, fps, duration_sec, class_list):
    n = int(round(duration_sec * fps))
    M = np.zeros((n, len(class_list)), dtype=bool)
    for ci, cname in enumerate(class_list):
        if cname not in gt_by_class:
            continue
        for (a, b) in gt_by_class[cname]:
            start = max(0, int(np.floor(a * fps)))
            end = min(n, int(np.ceil(b * fps)))
            if end > start:
                M[start:end, ci] = True
    return M

def per_class_prf_from_mats(gtM, prM, class_list):
    perclass = []
    TP_total = FP_total = FN_total = TN_total = 0
    for ci, cname in enumerate(class_list):
        y_true = gtM[:, ci]
        y_pred = prM[:, ci]
        TP = int(np.sum(y_true & y_pred))
        FP = int(np.sum(~y_true & y_pred))
        FN = int(np.sum(y_true & ~y_pred))
        TN = int(np.sum(~y_true & ~y_pred))
        P  = TP / (TP + FP) if (TP + FP) > 0 else 0.0
        R  = TP / (TP + FN) if (TP + FN) > 0 else 0.0
        F1 = 2 * P * R / (P + R) if (P + R) > 0 else 0.0
        perclass.append({"class": cname, "precision": P, "recall": R, "f1": F1, "support_frames": int(np.sum(y_true))})
        TP_total += TP; FP_total += FP; FN_total += FN; TN_total += TN
    macroP = float(np.mean([x["precision"] for x in perclass])) if perclass else 0.0
    macroR = float(np.mean([x["recall"] for x in perclass])) if perclass else 0.0
    macroF1= float(np.mean([x["f1"] for x in perclass])) if perclass else 0.0
    microP = TP_total / (TP_total + FP_total) if (TP_total + FP_total) > 0 else 0.0
    microR = TP_total / (TP_total + FN_total) if (TP_total + FN_total) > 0 else 0.0
    microF1= 2*microP*microR/(microP+microR) if (microP+microR) > 0 else 0.0
    overall_acc = (TP_total + TN_total) / (TP_total + FP_total + FN_total + TN_total) if (TP_total + FP_total + FN_total + TN_total) > 0 else 0.0
    return perclass, macroP, macroR, macroF1, microP, microR, microF1, overall_acc
