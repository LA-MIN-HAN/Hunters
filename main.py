import datetime
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
import pickle
import smtplib
import threading
import time
from tkinter import messagebox
import cv2
from PIL import Image, ImageTk
import customtkinter as ctk
import face_recognition
import pyttsx3

# --- UI Theme Setup ---
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

# --- Constants & Global Variables ---
ENCODINGS_FILE = "faces.pkl"
EMAILS_FILE = "emails.pkl"
TEMP_IMAGE = "temp_capture.jpg"

# Pre-configured Sender Credentials
SENDER_EMAIL = "laminhan212@gmail.com"
SENDER_PASSWORD = "xabb cgyb oebw maxz"

known_face_encodings = []
known_face_names = []
face_timestamps = []
registered_emails = {}


# --- Load Data Functions ---
def load_data():
  global known_face_encodings, known_face_names, face_timestamps, registered_emails
  if os.path.exists(ENCODINGS_FILE):
    with open(ENCODINGS_FILE, "rb") as f:
      data = pickle.load(f)
      known_face_encodings = data.get("encodings", [])
      known_face_names = data.get("names", [])
      face_timestamps = data.get("timestamps", [])
  if os.path.exists(EMAILS_FILE):
    with open(EMAILS_FILE, "rb") as f:
      loaded = pickle.load(f)
      if isinstance(loaded, list):
        registered_emails = {email: True for email in loaded}
      else:
        registered_emails = loaded


def save_encodings():
  with open(ENCODINGS_FILE, "wb") as f:
    pickle.dump(
        {
            "encodings": known_face_encodings,
            "names": known_face_names,
            "timestamps": face_timestamps,
        },
        f,
    )


def save_emails():
  with open(EMAILS_FILE, "wb") as f:
    pickle.dump(registered_emails, f)


load_data()


class SmartSecurityApp(ctk.CTk):

  def __init__(self):
    super().__init__()

    self.title("Smart Security Guard & Receptionist")
    self.geometry("1150x720")
    self.minsize(1050, 680)

    # State variables
    self.running = False
    self.cap = None
    self.unknown_last_alert = 0
    self.last_unknown_email_time = 0
    self.start_time = None

    # Track session-based alerts to strictly prevent duplicate emails/voice for known users
    self.welcomed_registered_users = set()
    self.emailed_registered_users = set()

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
    self.video_frame = ctk.CTkFrame(
        self, corner_radius=15, fg_color=("gray85", "gray15")
    )
    self.video_frame.grid(row=0, column=0, padx=15, pady=15, sticky="nsew")
    self.video_frame.grid_rowconfigure(0, weight=1)
    self.video_frame.grid_columnconfigure(0, weight=1)

    self.video_label = ctk.CTkLabel(
        self.video_frame,
        text="Camera Feed Offline",
        font=ctk.CTkFont(size=16, weight="bold"),
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

    # Management Actions Frame
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

    self.history_btn = ctk.CTkButton(
        self.mgmt_frame,
        text="📋 View & Manage Face History",
        command=self.view_face_history_gui,
        height=35,
        fg_color="#3b82f6",
        hover_color="#2563eb",
    )
    self.history_btn.grid(row=1, column=0, padx=15, pady=8, sticky="ew")

    self.manage_email_btn = ctk.CTkButton(
        self.mgmt_frame,
        text="📧 Manage Emails & Notifications",
        command=self.manage_emails_gui,
        height=35,
        fg_color="gray40",
        hover_color="gray30",
    )
    self.manage_email_btn.grid(
        row=2, column=0, padx=15, pady=(8, 15), sticky="ew"
    )

    # Log / Status Box
    self.log_textbox = ctk.CTkTextbox(
        self.control_frame, corner_radius=10, font=ctk.CTkFont(size=12)
    )
    self.log_textbox.grid(row=4, column=0, padx=20, pady=(0, 20), sticky="nsew")
    self.log_textbox.insert(
        "0.0", "System initialized successfully.\nReady to start...\n"
    )
    self.log_textbox.configure(state="disabled")

  def log_message(self, message):
    self.log_textbox.configure(state="normal")
    timestamp = datetime.datetime.now().strftime("[%H:%M:%S] ")
    self.log_textbox.insert("end", timestamp + message + "\n")
    self.log_textbox.see("end")
    self.log_textbox.configure(state="disabled")

  def speak(self, text):
    if self.engine:
      try:
        self.engine.say(text)
        self.engine.runAndWait()
      except Exception:
        pass

  def send_email_alert(self, subject, image_path):
    active_recipients = [
        email for email, active in registered_emails.items() if active
    ]
    if not active_recipients:
      return

    try:
      msg = MIMEMultipart()
      msg["Subject"] = subject
      msg["From"] = SENDER_EMAIL
      msg["To"] = ", ".join(active_recipients)

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
      server.login(SENDER_EMAIL, SENDER_PASSWORD)
      server.sendmail(SENDER_EMAIL, active_recipients, msg.as_string())
      server.quit()
      self.log_message(
          f"Email alert sent successfully to {len(active_recipients)} recipient(s)."
      )
    except Exception as e:
      self.log_message(f"Email failed: {str(e)}")

  def start_system(self):
    if self.running:
      return
    self.cap = cv2.VideoCapture(0)
    if not self.cap.isOpened():
      messagebox.showerror("Error", "Could not open webcam.")
      return

    self.running = True
    self.start_time = time.time()
    # Reset tracking sets on system start
    self.welcomed_registered_users.clear()
    self.emailed_registered_users.clear()
    self.unknown_last_alert = 0
    self.last_unknown_email_time = 0

    self.status_badge.configure(
        text=" ● System Status: RUNNING ", text_color="#2fa572"
    )
    self.start_btn.configure(state="disabled")
    self.stop_btn.configure(state="normal")
    self.log_message("System started.")

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

          # 1. Voice Greeting: Exactly ONE time per session for this registered user
          if name not in self.welcomed_registered_users:
            self.welcomed_registered_users.add(name)
            # Correct Japanese structure: "Irasshaimase [Name] san"
            greeting_text = f"いらっしゃいませ {name} さん"
            threading.Thread(
                target=self.speak, args=(greeting_text,), daemon=True
            ).start()
            self.log_message(f"Welcomed: {name}")

          # 2. Email Alert: Exactly ONE time per session for this registered user
          if name not in self.emailed_registered_users:
            self.emailed_registered_users.add(name)
            cv2.imwrite(TEMP_IMAGE, frame)
            threading.Thread(
                target=self.send_email_alert,
                args=(f"Known Visitor Alert: {name}", TEMP_IMAGE),
            ).start()
            self.log_message(f"Email sent for Known Visitor: {name}")

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

          # Unknown face voice every 10 seconds
          if current_time - self.unknown_last_alert >= 10:
            self.unknown_last_alert = current_time
            threading.Thread(
                target=self.speak, args=("誰さんですか",), daemon=True
            ).start()
            self.log_message("Unknown visitor detected: Spoken ('誰さんですか').")

          # Unknown face email every 30 seconds
          if current_time - self.last_unknown_email_time >= 30:
            self.last_unknown_email_time = current_time
            cv2.imwrite(TEMP_IMAGE, frame)
            threading.Thread(
                target=self.send_email_alert,
                args=("Unknown Intruder / Visitor Alert", TEMP_IMAGE),
            ).start()
            self.log_message("Unknown visitor detected: Email sent (30s interval).")

      cv2_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
      pil_image = Image.fromarray(cv2_image)

      w = self.video_frame.winfo_width() - 20
      h = self.video_frame.winfo_height() - 20
      if w > 10 and h > 10:
        pil_image = pil_image.resize((w, h), Image.Resampling.LANCZOS)

      imgtk = ctk.CTkImage(
          light_image=pil_image, dark_image=pil_image, size=(w, h)
      )
      self.video_label.configure(image=imgtk, text="")
      self.video_label.image = imgtk

  def add_face_gui(self):
    dialog = ctk.CTkInputDialog(
        text="Enter visitor's name:", title="Register Face"
    )
    name = dialog.get_input()
    if not name:
      return

    reg_win = ctk.CTkToplevel(self)
    reg_win.title(f"Registering Face: {name}")
    reg_win.geometry("550x500")
    reg_win.grab_set()

    lbl_info = ctk.CTkLabel(
        reg_win,
        text=f"Position your face clearly, then click 'Capture & Train'.",
        font=ctk.CTkFont(size=14, weight="bold"),
    )
    lbl_info.pack(padx=20, pady=10)

    cam_lbl = ctk.CTkLabel(reg_win, text="Loading Camera...", width=480, height=320)
    cam_lbl.pack(padx=20, pady=5)

    cap = cv2.VideoCapture(0)
    capturing_active = [True]

    def update_reg_preview():
      while capturing_active[0] and cap.isOpened():
        ret, frame = cap.read()
        if ret:
          cv2_img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
          pil_img = Image.fromarray(cv2_img).resize((480, 320))
          ctk_img = ctk.CTkImage(
              light_image=pil_img, dark_image=pil_img, size=(480, 320)
          )
          try:
            cam_lbl.configure(image=ctk_img, text="")
            cam_lbl.image = ctk_img
          except Exception:
            break
        time.sleep(0.03)

    threading.Thread(target=update_reg_preview, daemon=True).start()

    def capture_and_process():
      capturing_active[0] = False
      ret, frame = cap.read()
      cap.release()

      if ret:
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        encodings = face_recognition.face_encodings(rgb_frame)
        if encodings:
          timestamp_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
          known_face_encodings.append(encodings[0])
          known_face_names.append(name)
          face_timestamps.append(timestamp_str)
          save_encodings()

          messagebox.showinfo(
              "Success", f"Successfully Done!\nFace registered for {name}."
          )
          self.log_message(
              f"Successfully Done: New face added -> {name} at {timestamp_str}"
          )
          reg_win.destroy()
        else:
          messagebox.showerror(
              "Error / Failed",
              "Could not detect a face clearly!\nPlease try again and"
              " position properly.",
          )
          reg_win.destroy()
      else:
        messagebox.showerror("Error", "Failed to capture image from camera.")
        reg_win.destroy()

    capture_btn = ctk.CTkButton(
        reg_win,
        text="📸 Capture & Train",
        command=capture_and_process,
        fg_color="#2fa572",
        hover_color="#248259",
        height=40,
        font=ctk.CTkFont(size=14, weight="bold"),
    )
    capture_btn.pack(padx=20, pady=15, fill="x")

  def view_face_history_gui(self):
    history_win = ctk.CTkToplevel(self)
    history_win.title("Registered Face History & Management")
    history_win.geometry("500x450")
    history_win.grab_set()

    title_lbl = ctk.CTkLabel(
        history_win,
        text="📜 Registered Faces & Timestamps",
        font=ctk.CTkFont(size=16, weight="bold"),
    )
    title_lbl.pack(padx=20, pady=(20, 10))

    scroll_frame = ctk.CTkScrollableFrame(history_win, width=440, height=300)
    scroll_frame.pack(padx=20, pady=10, fill="both", expand=True)

    def refresh_history_list():
      for widget in scroll_frame.winfo_children():
        widget.destroy()

      if not known_face_names:
        lbl = ctk.CTkLabel(
            scroll_frame, text="No registered faces found.", text_color="gray"
        )
        lbl.pack(pady=20)
      else:
        for i, name in enumerate(known_face_names):
          ts = (
              face_timestamps[i]
              if i < len(face_timestamps)
              else "Unknown Date"
          )
          item_frame = ctk.CTkFrame(scroll_frame, fg_color=("gray90", "gray20"))
          item_frame.pack(padx=5, pady=5, fill="x")

          info_text = f"👤 {name}   🕒 {ts}"
          info_lbl = ctk.CTkLabel(
              item_frame,
              text=info_text,
              font=ctk.CTkFont(size=12, weight="bold"),
          )
          info_lbl.pack(side="left", padx=10, pady=8)

          del_btn = ctk.CTkButton(
              item_frame,
              text="🗑️ Delete",
              width=70,
              height=28,
              fg_color="#d9534f",
              hover_color="#b52b27",
              command=lambda idx=i, n=name: delete_face_index(idx, n),
          )
          del_btn.pack(side="right", padx=10, pady=6)

    def delete_face_index(idx, name):
      if messagebox.askyesno(
          "Confirm Delete", f"Are you sure you want to delete '{name}'?"
      ):
        if idx < len(known_face_encodings):
          known_face_encodings.pop(idx)
        if idx < len(known_face_names):
          known_face_names.pop(idx)
        if idx < len(face_timestamps):
          face_timestamps.pop(idx)

        save_encodings()
        refresh_history_list()
        self.log_message(f"Deleted registered face: {name}")

    refresh_history_list()

  def manage_emails_gui(self):
    email_win = ctk.CTkToplevel(self)
    email_win.title("Manage Emails & Notifications")
    email_win.geometry("480x450")
    email_win.grab_set()

    title_lbl = ctk.CTkLabel(
        email_win,
        text="📧 Alert Email Settings",
        font=ctk.CTkFont(size=16, weight="bold"),
    )
    title_lbl.pack(padx=20, pady=(20, 10))

    scroll_frame = ctk.CTkScrollableFrame(email_win, width=420, height=230)
    scroll_frame.pack(padx=20, pady=5, fill="both", expand=True)

    checkbox_vars = {}

    def refresh_email_list():
      for widget in scroll_frame.winfo_children():
        widget.destroy()
      checkbox_vars.clear()

      if not registered_emails:
        lbl = ctk.CTkLabel(
            scroll_frame, text="No emails registered yet.", text_color="gray"
        )
        lbl.pack(pady=20)
      else:
        for email, active in registered_emails.items():
          var = ctk.BooleanVar(value=active)
          checkbox_vars[email] = var

          cb = ctk.CTkCheckBox(
              scroll_frame,
              text=email,
              variable=var,
              command=lambda e=email, v=var: update_email_status(e, v),
          )
          cb.pack(padx=10, pady=6, anchor="w")

    def update_email_status(email, var):
      registered_emails[email] = var.get()
      save_emails()
      self.log_message(
          f"Email notification for {email} set to: {registered_emails[email]}"
      )

    refresh_email_list()

    action_frame = ctk.CTkFrame(email_win, fg_color="transparent")
    action_frame.pack(padx=20, pady=15, fill="x")
    action_frame.grid_columnconfigure((0, 1), weight=1)

    def add_new_email_action():
      dialog = ctk.CTkInputDialog(
          text="Enter new recipient email:", title="Add Email"
      )
      new_email = dialog.get_input()
      if new_email:
        if "@" not in new_email or "." not in new_email:
          messagebox.showerror("Error", "Invalid email format.")
          return
        if new_email in registered_emails:
          messagebox.showwarning("Warning", "Email already exists.")
          return
        registered_emails[new_email] = True
        save_emails()
        refresh_email_list()
        self.log_message(f"Added new email: {new_email}")

    def delete_selected_action():
      to_delete = [
          email for email, var in checkbox_vars.items() if not var.get()
      ]
      if not to_delete:
        messagebox.showinfo(
            "Info",
            "Please uncheck the email(s) you want to delete from the list first,"
            " then click Delete.",
        )
        return

      if messagebox.askyesno(
          "Confirm Delete",
          f"Delete {len(to_delete)} selected email(s) from the list?",
      ):
        for email in to_delete:
          del registered_emails[email]
        save_emails()
        refresh_email_list()
        self.log_message(f"Deleted email(s): {to_delete}")

    add_btn = ctk.CTkButton(
        action_frame,
        text="➕ Add New Email",
        command=add_new_email_action,
        fg_color="#2fa572",
        hover_color="#248259",
    )
    add_btn.grid(row=0, column=0, padx=(0, 5), sticky="ew")

    del_btn = ctk.CTkButton(
        action_frame,
        text="🗑️ Delete Selected",
        command=delete_selected_action,
        fg_color="#d9534f",
        hover_color="#b52b27",
    )
    del_btn.grid(row=0, column=1, padx=(5, 0), sticky="ew")


if __name__ == "__main__":
  app = SmartSecurityApp()
  app.mainloop()