import cv2
import time
import numpy as np
import smtplib
import threading
import math
import tkinter as tk
from tkinter import messagebox
import pyrealsense2 as rs
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage

SENDER_EMAIL = "laminhan212@gmail.com"
SENDER_PASSWORD = "xabb cgyb oebw maxz"

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
MIN_MOTION_AREA = 5000
COOLDOWN_SECONDS = 10

is_system_running = False
pipeline = None

def send_alert_email(image_path, recipient_list):
    if not recipient_list:
        return
        
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
        
        server.sendmail(SENDER_EMAIL, recipient_list, msg.as_string())
        server.quit()
        print("[INFO] Email alert sent simultaneously to:", recipient_list)
    except Exception as e:
        print(f"[ERROR] Email failed to send: {e}")

def run_motion_detection(recipient_list):
    global is_system_running, pipeline
    
    pipeline = rs.pipeline()
    config = rs.config()
    config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)

    print("[INFO] Starting Intel RealSense camera pipeline...")
    pipeline.start(config)

    time.sleep(2)
    prev_frame = None
    last_email_time = 0

    print("[INFO] Security system activated. Monitoring...")

    try:
        while is_system_running:
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
                    print("[ALERT] Motion detected! Dispatching email...")
                    img_filename = "motion_alert.jpg"
                    cv2.imwrite(img_filename, frame)
                    
                    send_alert_email(img_filename, recipient_list)
                    last_email_time = current_time

            cv2.imshow("Intel RealSense Security Feed", frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    except Exception as e:
        print(f"[ERROR] Security system loop error: {e}")

    finally:
        if pipeline:
            pipeline.stop()
        cv2.destroyAllWindows()
        is_system_running = False

class PlaceholderEntry(tk.Entry):
    def __init__(self, master=None, placeholder="example@gmail.com", color='#888888', **kw):
        super().__init__(master, **kw)
        self.placeholder = placeholder
        self.placeholder_color = color
        self.default_fg_color = self['fg']

        self.bind("<FocusIn>", self._focus_in)
        self.bind("<FocusOut>", self._focus_out)
        self.put_placeholder()

    def put_placeholder(self):
        self.insert(0, self.placeholder)
        self['fg'] = self.placeholder_color

    def _focus_in(self, *args):
        if self['fg'] == self.placeholder_color:
            self.delete('0', 'end')
            self['fg'] = self.default_fg_color

    def _focus_out(self, *args):
        if not self.get():
            self.put_placeholder()

class SecurityApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🐾 Animated Security Guard System 🐾")
        self.root.geometry("650x700")
        self.root.configure(bg="#FFFFFF")

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        self.bg_canvas = tk.Canvas(root, bg="#FFFFFF", highlightthickness=0)
        self.bg_canvas.grid(row=0, column=0, sticky="nsew")

        self.pet_shapes = [
            {"x": 60, "y": 80, "dx": 2, "dy": 1.5, "emoji": "🐶"},
            {"x": 560, "y": 90, "dx": -1.5, "dy": 2, "emoji": "🐱"},
            {"x": 70, "y": 580, "dx": 1.8, "dy": -1.2, "emoji": "🐰"},
            {"x": 550, "y": 600, "dx": -2, "dy": -1.5, "emoji": "🦊"},
            {"x": 300, "y": 50, "dx": 1, "dy": 1.8, "emoji": "🐼"}
        ]
        self.pet_items = []
        for pet in self.pet_shapes:
            item = self.bg_canvas.create_text(pet["x"], pet["y"], text=pet["emoji"], font=("Segoe UI Emoji", 26))
            self.pet_items.append(item)

        self.animate_background()

        self.content_frame = tk.Frame(self.bg_canvas, bg="#FFFFFF")
        self.bg_canvas.create_window(325, 350, window=self.content_frame, anchor="center")

        self.bg_canvas.bind("<Configure>", self.on_canvas_resize)

        title_lbl = tk.Label(self.content_frame, text="Security Alert System", font=("Arial", 18, "bold"), bg="#FFFFFF", fg="#333333")
        title_lbl.pack(pady=5)

        sub_lbl = tk.Label(self.content_frame, text="Enter your email address to receive notifications", font=("Arial", 11), bg="#FFFFFF", fg="#666666")
        sub_lbl.pack(pady=3)

        self.email_rows = []

        self.email_container = tk.Frame(self.content_frame, bg="#FFFFFF")
        self.email_container.pack(pady=15)

        self.add_btn = tk.Button(
            self.content_frame, 
            text="➕ Add another email address", 
            font=("Arial", 11, "bold"), 
            bg="#FF1493", 
            fg="white", 
            activebackground="#FF69B4", 
            activeforeground="white",
            relief="flat", 
            bd=0, 
            cursor="hand2",
            command=self.add_email_field
        )
        self.add_btn.pack(pady=8, ipadx=12, ipady=6)

        self.start_btn = tk.Button(
            self.content_frame, 
            text="🚀 Start Security System", 
            font=("Arial", 13, "bold"), 
            bg="#32CD32", 
            fg="white", 
            activebackground="#2E8B57", 
            activeforeground="white",
            relief="flat", 
            bd=0, 
            cursor="hand2",
            command=self.toggle_system
        )
        self.start_btn.pack(pady=12, ipadx=24, ipady=8)

        self.add_email_field()

    def animate_background(self):
        w = self.bg_canvas.winfo_width() or 650
        h = self.bg_canvas.winfo_height() or 700

        for i, pet in enumerate(self.pet_shapes):
            pet["x"] += pet["dx"]
            pet["y"] += pet["dy"]

            if pet["x"] <= 30 or pet["x"] >= w - 30:
                pet["dx"] *= -1
            if pet["y"] <= 30 or pet["y"] >= h - 30:
                pet["dy"] *= -1

            self.bg_canvas.coords(self.pet_items[i], pet["x"], pet["y"])

        self.root.after(40, self.animate_background)

    def on_canvas_resize(self, event):
        self.bg_canvas.coords(1, event.width / 2, event.height / 2)

    def add_email_field(self):
        row_frame = tk.Frame(self.email_container, bg="#FFFFFF")
        row_frame.pack(fill="x", pady=4)

        lbl = tk.Label(row_frame, text="Email:", font=("Arial", 11, "bold"), bg="#FFFFFF", fg="#333333")
        lbl.pack(side=tk.LEFT, padx=4)

        entry = PlaceholderEntry(row_frame, placeholder="example@gmail.com", font=("Arial", 11), width=32, relief="solid", bd=1)
        entry.pack(side=tk.LEFT, padx=6, ipady=4)

        del_btn = tk.Button(row_frame, text="❌ Delete", font=("Arial", 9, "bold"), bg="#FF4500", fg="white", activebackground="#CD5C5C", relief="flat", cursor="hand2", command=lambda: self.delete_email_field(row_frame))
        del_btn.pack(side=tk.LEFT, padx=4)

        self.email_rows.append((row_frame, entry))

    def delete_email_field(self, row_frame):
        if len(self.email_rows) <= 1:
            messagebox.showwarning("Warning", "At least one email address is required!")
            return
        
        self.email_rows = [r for r in self.email_rows if r[0] != row_frame]
        row_frame.destroy()

    def get_emails(self):
        emails = []
        for _, entry in self.email_rows:
            val = entry.get().strip()
            if val and val != "example@gmail.com":
                emails.append(val)
        return emails

    def toggle_system(self):
        global is_system_running
        
        if not is_system_running:
            emails = self.get_emails()
            if not emails:
                messagebox.showerror("Error", "Please enter at least one valid Email address!")
                return

            is_system_running = True
            self.start_btn.config(text="🛑 Stop Security System", bg="#DC143C")
            
            threading.Thread(target=run_motion_detection, args=(emails,), daemon=True).start()
            messagebox.showinfo("Success", f"Security System Started!\nMonitoring for alerts to {len(emails)} email(s).")
        else:
            is_system_running = False
            self.start_btn.config(text="🚀 Start Security System", bg="#32CD32")
            messagebox.showinfo("Stopped", "Security System has been stopped.")

if __name__ == "__main__":
    root = tk.Tk()
    app = SecurityApp(root)
    root.mainloop()