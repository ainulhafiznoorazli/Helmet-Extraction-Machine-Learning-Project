Helmet Compliance Detection System

A real-time, multi-class helmet compliance detection system built using YOLOv8, Flask, and OpenCV. The system identifies fine-grain PPE states such as helmet missing, helmet false, helmet poor fit, helmet not secure, and more. It includes:

Live webcam helmet detection

Video experimentation and automatic metric scoring (Precision, Recall, F1, Macro/Micro scores)

Dashboard visualization for experiment summaries

Support for YOLOv8n and YOLOv8s model weights

This project demonstrates an end-to-end deployment pipeline for real-time workplace safety monitoring.

How to Use This Project
1. Prepare the Environment

Use Python 3.10.8 (recommended for YOLO compatibility).

Create and activate your YOLO virtual environment:

(or your preferred environment manager)

2. Place All Required Files Together

Ensure the following are all in the same project folder:

app.py

routes.py

model_utils.py

ui_templates.py

Both YOLO weight files:

yolov8n.pt

yolov8s.pt

3. Install Dependencies

Install required packages (Flask, OpenCV, Ultralytics, NumPy, Pandas, etc.).
If you have a requirements.txt, use:


4. Run the Application

Start the app by running:

python app.py

The terminal will show a Localhost URL, typically:

http://127.0.0.1:5000/

Open this in your browser to access the system.

5. Features Available in the Web App

Live Stream
Real-time YOLO helmet detection through your webcam.

Experimentation
Upload videos (and optional ground-truth JSON files) to compute detailed performance metrics.

Dashboard
View summarized experiment results including macro/micro scores, class-level performance, and charts.
