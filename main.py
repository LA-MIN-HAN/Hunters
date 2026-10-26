import datetime
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
import pickle
import smtplib
import threading
import time
from tkinter import messagebox, simpledialog
import cv2
from PIL import Image, ImageTk
import customtkinter as ctk  # Modern UI library
import face_recognition
import pyttsx3

# --- UI Theme Setup ---
ctk.set_appearance_mode("System")  # Options: "System", "Dark", "Light"
ctk.set_default_color_theme("blue")  # Options: "blue", "green", "dark-blue"

# --- Constants & Global Variables ---
ENCODINGS_FILE = "faces.pkl"
EMAILS_FILE = "emails.pkl"
TEMP_IMAGE = "temp_capture.jpg"

known_face_encodings = []
known_face_names = []
registered_emails = []


# --- Load Data Functions ---
def load_data():
  global known_face_encodings, known_face_names, registered_emails
  if os.path.exists(ENCODINGS_FILE):
    with open(ENCODINGS_FILE, "rb") as f:
      data = pickle.load(f)
      known_face_encodings = data.get("encodings", [])
      known_face_names = data.get("names", [])
  if os.path.exists(EMAILS_FILE):
    with open(EMAILS_FILE, "rb") as f:
      registered_emails = pickle.load(f)


def save_encodings():
  with open(ENCODINGS_FILE, "wb") as f:
    pickle.dump(
        {"encodings": known_face_encodings, "names": known_face_names}, f
    )


def save_emails():
  with open(EMAILS_FILE, "wb") as f:
    pickle.dump(registered_emails, f)


load_data()


class SmartSecurityApp(ctk.CTk):

  def __init__(self):
    super().__init__()

    self.title("Smart Security Guard & Receptionist")
    self.geometry("1100x700")
    self.minsize(1000, 650)

    # State variables
    self.running = False
    self.cap = None
    self.last_alert_time = {}
    self.unknown_last_alert = 0
    self.start_time = None

    # Initialize Text-to-Speech Engine
    try:
      self.engine = pyttsx3.init()
      self.engine.setProperty("rate", 150)
    except Exception:
      self.engine = None

    # --- Layout Grid ---
    self.grid_columnconfigure(0, weight=3)  # Video Area
    self.grid_columnconfigure(1, weight=2)  # Control Panel
    self.grid_rowconfigure(0, weight=1)

    # --- Left Frame: Video Feed ---
    self.video_frame = ctk.CTkFrame(self, corner_radius=15, fg_color=("gray85", "gray15"))
    self.video_frame.grid(row=0, column=0, padx=15, pady=15, sticky="nsew")
    self.video_frame.grid_rowconfigure(0, weight=1)
    self.video_frame.grid_columnconfigure(0, weight=1)

    self.video_label = ctk.CTkLabel(
        self.video_frame, text="Camera Feed Offline", font=ctk.CTkFont(size=16, weight="bold")
    )
    self.video_label.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

    # --- Right Frame: Control Panel ---
    self.control_frame = ctk.CTkFrame(self, corner_radius=15)
    self.control_frame.grid(row=0, column=1, padx=(0, 15), pady=15, sticky="nsew")
    self.control_frame.grid_columnconfigure(0, weight=1)
    self.control_frame.grid_rowconfigure(4, weight=1)

    # App Title Header
    self.title_label = ctk.CTkLabel(
        self.control_frame,
        text="🛡️ Kamata-sai Security",
        font=ctk.CTkFont(size=22, weight="bold"),
    )
    self.title_label.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")

    # System Status Indicator
    self.status_badge = ctk.CTkLabel(
        self.control_frame,
        text=" ● System Status: STOPPED ",
        font=ctk.CTkFont(size=13, weight="bold"),
        text_color="orange",
    )
    self.status_badge.grid(row=1, column=0, padx=20, pady=(0, 15), sticky="w")

    # Start/Stop Buttons Frame
    self.btn_frame = ctk.CTkFrame(self.control_frame, fg_color="transparent")
    self.btn_frame.grid(row=2, column=0, padx=20, pady=10, sticky="ew")
    self.btn_frame.grid_columnconfigure((0, 1), weight=1)

    self.start_btn = ctk.CTkButton(
        self.btn_frame,
        text="Start System",
        fg_color="#2fa572",
        hover_color="#248259",
        command=self.start_system,
        font=ctk.CTkFont(size=14, weight="bold"),
        height=40,
    )
    self.start_btn.grid(row=0, column=0, padx=(0, 5), sticky="ew")

    self.stop_btn = ctk.CTkButton(
        self.btn_frame,
        text="Stop System",
        fg_color="#d9534f",
        hover_color="#b52b27",
        command=self.stop_system,
        font=ctk.CTkFont(size=14, weight="bold"),
        height=40,
        state="disabled",
    )
    self.stop_btn.grid(row=0, column=1, padx=(5, 0), sticky="ew")

    # Management Actions Frame (Add Face / Manage Emails)
    self.mgmt_frame = ctk.CTkFrame(self.control_frame, corner_radius=10)
    self.mgmt_frame.grid(row=3, column=0, padx=20, pady=15, sticky="ew")
    self.mgmt_frame.grid_columnconfigure(0, weight=1)

    self.add_face_btn = ctk.CTkButton(
        self.mgmt_frame,
        text="➕ Register New Face",
        command=self.add_face_gui,
        height=35,
    )
    self.add_face_btn.grid(row=0, column=0, padx=15, pady=(15, 8), sticky="ew")

    self.manage_email_btn = ctk.CTkButton(
        self.mgmt_frame,
        text="📧 Manage Emails",
        command=self.manage_emails_gui,
        height=35,
        fg_color="gray40",
        hover_color="gray30",
    )
    self.manage_email_btn.grid(row=1, column=0, padx=15, pady=(8, 15), sticky="ew")

    # Log / Status Box
    self.log_textbox = ctk.CTkTextbox(
        self.control_frame, corner_radius=10, font=ctk.CTkFont(size=12)
    )
    self.log_textbox.grid(row=4, column=0, padx=20, pady=(0, 20), sticky="nsew")
    self.log_textbox.insert("0.0", "System initialized successfully.\nReady to start...\n")
    self.log_textbox.configure(state="disabled")

  def log_message(self, message):
    self.log_textbox.configure(state="normal")
    timestamp = datetime.datetime.now().strftime("[%H:%M:%S] ")
    self.log_textbox.insert("end", timestamp + message + "\n")
    self.log_textbox.see("end")
    self.log_textbox.configure(state="disabled")

  # --- Core Voice & Email Logic (Preserved) ---
  def speak(self, text):
    if self.engine:
      try:
        self.engine.say(text)
        self.engine.runAndWait()
      except Exception:
        pass

  def send_email_alert(self, subject, image_path):
    if not registered_emails:
      return
    sender_email = "laminhan221@gmail.com"  # Change accordingly
    sender_password = "xabb cgyb oebw maxz"  # Change accordingly

    try:
      msg = MIMEMultipart()
      msg["Subject"] = subject
      msg["From"] = sender_email
      msg["To"] = ", ".join(registered_emails)

      body = MIMEText(
          f"Alert triggered at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
      )
      msg.attach(body)

      if os.path.exists(image_path):
        with open(image_path, "rb") as f:
          img_data = f.read()
        img = MIMEImage(img_data, name="capture.jpg")
        msg.attach(img)

      server = smtplib.SMTP("smtp.gmail.com", 587)
      server.starttls()
      server.login(sender_email, sender_password)
      server.sendmail(sender_email, registered_emails, msg.as_string())
      server.quit()
      self.log_message("Email alert sent successfully.")
    except Exception as e:
      self.log_message(f"Email failed: {str(e)}")

  # --- System Controls ---
  def start_system(self):
    if self.running:
      return
    self.cap = cv2.VideoCapture(0)
    if not self.cap.isOpened():
      messagebox.showerror("Error", "Could not open webcam.")
      return

    self.running = True
    self.start_time = time.time()
    self.status_badge.configure(text=" ● System Status: RUNNING ", text_color="#2fa572")
    self.start_btn.configure(state="disabled")
    self.stop_btn.configure(state="normal")
    self.log_message("System started.")

    # Run video loop in a thread
    self.thread = threading.Thread(target=self.video_loop, daemon=True)
    self.thread.start()

  def stop_system(self):
    self.running = False
    if self.cap:
      self.cap.release()
    self.status_badge.configure(text=" ● System Status: STOPPED ", text_color="orange")
    self.start_btn.configure(state="normal")
    self.stop_btn.configure(state="disabled")
    self.video_label.configure(image="", text="Camera Feed Offline")
    self.log_message("System stopped.")

  def video_loop(self):
    while self.running:
      ret, frame = self.cap.read()
      if not ret:
        break

      small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
      rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

      face_locations = face_recognition.face_locations(rgb_small_frame)
      face_encodings = face_recognition.face_encodings(
          rgb_small_frame, face_locations
      )

      current_time = time.time()

      for face_encoding, face_location in zip(face_encodings, face_locations):
        matches = face_recognition.compare_faces(
            known_face_encodings, face_encoding
        )
        name = "Unknown"

        if True in matches:
          first_match_index = matches.index(True)
          name = known_face_names[first_match_index]

          # Scale back face locations
          top, right, bottom, left = [v * 4 for v in face_location]
          cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
          cv2.putText(
              frame,
              name,
              (left, top - 10),
              cv2.FONT_HERSHEY_SIMPLEX,
              0.75,
              (0, 255, 0),
              2,
          )

          # Known user greeting logic
          if (
              name not in self.last_alert_time
              or current_time - self.last_alert_time[name] > 300
          ):
            self.last_alert_time[name] = current_time
            cv2.imwrite(TEMP_IMAGE, frame)
            threading.Thread(
                target=self.speak, args=(f"いらっしゃいませ {name} さん",)
            ).start()
            threading.Thread(
                target=self.send_email_alert,
                args=(f"Known Visitor Alert: {name}", TEMP_IMAGE),
            ).start()
            self.log_message(f"Recognized: {name}")

        else:
          top, right, bottom, left = [v * 4 for v in face_location]
          cv2.rectangle(frame, (left, top), (right, bottom), (0, 0, 255), 2)
          cv2.putText(
              frame,
              "Unknown",
              (left, top - 10),
              cv2.FONT_HERSHEY_SIMPLEX,
              0.75,
              (0, 0, 255),
              2,
          )

          # Unknown user logic
          elapsed_since_start = current_time - self.start_time
          if elapsed_since_start < 20:
            if current_time - self.unknown_last_alert > 10:
              self.unknown_last_alert = current_time
              cv2.imwrite(TEMP_IMAGE, frame)
              threading.Thread(
                  target=self.speak, args=("誰さんですか",)
              ).start()
              threading.Thread(
                  target=self.send_email_alert,
                  args=("Unknown Visitor Alert", TEMP_IMAGE),
              ).start()
              self.log_message("Unknown visitor detected (Startup phase).")
          else:
            if current_time - self.unknown_last_alert > 3600:
              self.unknown_last_alert = current_time
              cv2.imwrite(TEMP_IMAGE, frame)
              threading.Thread(
                  target=self.speak, args=("誰さんですか",)
              ).start()
              threading.Thread(
                  target=self.send_email_alert,
                  args=("Unknown Intruder Alert", TEMP_IMAGE),
              ).start()
              self.log_message("Unknown intruder detected.")

      # Convert frame to display in CTkLabel
      cv2_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
      pil_image = Image.fromarray(cv2_image)

      # Resize to fit UI video frame smoothly
      w = self.video_frame.winfo_width() - 20
      h = self.video_frame.winfo_height() - 20
      if w > 10 and h > 10:
        pil_image = pil_image.resize((w, h), Image.Resampling.LANCZOS)

      imgtk = ctk.CTkImage(light_image=pil_image, dark_image=pil_image, size=(w, h))
      self.video_label.configure(image=imgtk, text="")
      self.video_label.image = imgtk

  # --- Add Face & Email Management Dialogs ---
  def add_face_gui(self):
    name = simpledialog.askstring("Register Face", "Enter visitor's name:")
    if not name:
      return

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
      messagebox.showerror("Error", "Cannot access camera.")
      return

    messagebox.showinfo(
        "Capture",
        f"Position your face for {name}. Click OK to capture snapshot.",
    )
    ret, frame = cap.read()
    cap.release()

    if ret:
      rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
      encodings = face_recognition.face_encodings(rgb_frame)
      if encodings:
        known_face_encodings.append(encodings[0])
        known_face_names.append(name)
        save_encodings()
        messagebox.load = "Success"
        messagebox.showinfo("Success", f"Face registered successfully for {name}!")
        self.log_message(f"New face added: {name}")
      else:
        messagebox.showerror(
            "Error", "No face detected in the frame. Please try again."
        )
    else:
      messagebox.showerror("Error", "Failed to capture image from camera.")

  def manage_emails_gui(self):
    email = simpledialog.askstring(
        "Manage Emails",
        f"Current emails: {registered_emails}\n\nEnter email to add (or type 'clear' to reset):",
    )
    if email:
      if email.lower() == "clear":
        registered_emails.clear()
        save_emails()
        self.log_message("Email list cleared.")
      else:
        if email not in registered_emails:
          registered_emails.append(email)
          save_emails()
          self.log_message(f"Added email: {email}")
          messagebox.showinfo("Success", f"Added {email} to alert list.")


if __name__ == "__main__":
  app = SmartSecurityApp()
  app.mainloop()