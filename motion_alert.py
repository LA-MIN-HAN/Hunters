import cv2
import time
import numpy as np
import smtplib
import pyrealsense2 as rs
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage

SENDER_EMAIL = "laminhan212@gmail.com"
SENDER_PASSWORD = "xabb cgyb oebw maxz"

RECEIVER_EMAILS = [
    "laminhan212@gmail.com",
    "hsiha.jp@gmail.com",
    "htatmyatlin1712@gmail.com",
    "khantnaingtun999@gmail.com"

]
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

MIN_MOTION_AREA = 5000
COOLDOWN_SECONDS = 60
last_email_time = 0

def send_alert_email(image_path):
    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = SENDER_EMAIL
    msg['Subject'] = "ALERT: Motion Detected from RealSense Camera"

    body = "Motion was detected. Please check the attached photo from Intel RealSense D435i."
    msg.attach(MIMEText(body, 'plain'))

    try:
        with open(image_path, 'rb') as f:
            img = MIMEImage(f.read())
            img.add_header('Content-Disposition', 'attachment', filename="motion.jpg")
            msg.attach(img)

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAILS, msg.as_string())
        server.quit()
        print("[INFO] Email alert sent simultaneously to all personal Gmail addresses.")
    except Exception as e:
        print(f"[ERROR] Email failed to send: {e}")

pipeline = rs.pipeline()
config = rs.config()
config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)

print("[INFO] Starting Intel RealSense camera pipeline...")
pipeline.start(config)

time.sleep(2)
prev_frame = None

print("[INFO] Security system activated. Monitoring...")

try:
    while True:
        frames = pipeline.wait_for_frames()
        color_frame = frames.get_color_frame()
        if not color_frame:
            continue

        frame = np.asanyarray(color_frame.get_data())

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        if prev_frame is None:
            prev_frame = gray
            continue

        frame_delta = cv2.absdiff(prev_frame, gray)
        thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
        thresh = cv2.dilate(thresh, None, iterations=2)

        contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        motion_detected = False

        for contour in contours:
            if cv2.contourArea(contour) < MIN_MOTION_AREA:
                continue
            
            motion_detected = True
            (x, y, w, h) = cv2.boundingRect(contour)
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)

        prev_frame = gray

        if motion_detected:
            current_time = time.time()
            if current_time - last_email_time > COOLDOWN_SECONDS:
                print("[ALERT] Motion detected! Saving image and dispatching email...")
                img_filename = "motion_alert.jpg"
                cv2.imwrite(img_filename, frame)
                
                send_alert_email(img_filename)
                last_email_time = current_time
            else:
                remaining_time = int(COOLDOWN_SECONDS - (current_time - last_email_time))
                print(f"[STATUS] Motion detected during cooldown. Next email in {remaining_time}s.")

        cv2.imshow("Intel RealSense Security Feed", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

except KeyboardInterrupt:
    print("[INFO] Stopping system...")

finally:
    pipeline.stop()
    cv2.destroyAllWindows()