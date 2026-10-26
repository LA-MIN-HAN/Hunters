import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import cv2
import PIL.Image, PIL.ImageTk
import face_recognition
import pyttsx3
import threading
import time
import pickle
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage

ENGINE = pyttsx3.init()
ENGINE.setProperty('rate', 150)

FACES_FILE = "faces.pkl"
EMAILS_FILE = "emails.txt"

KNOWN_FACE_ENCODINGS = []
KNOWN_FACE_NAMES = []

if os.path.exists(FACES_FILE):
    with open(FACES_FILE, "rb") as f:
        data = pickle.load(f)
        KNOWN_FACE_ENCODINGS = data.get("encodings", [])
        KNOWN_FACE_NAMES = data.get("names", [])

def save_faces():
    data = {"encodings": KNOWN_FACE_ENCODINGS, "names": KNOWN_FACE_NAMES}
    with open(FACES_FILE, "wb") as f:
        pickle.dump(data, f)

def load_emails():
    if not os.path.exists(EMAILS_FILE):
        return []
    with open(EMAILS_FILE, "r") as f:
        return [line.strip() for line in f if line.strip()]

def save_emails_list(emails):
    with open(EMAILS_FILE, "w") as f:
        for email in emails:
            f.write(email + "\n")

class App:
    def __init__(self, window, window_title):
        self.window = window
        self.window.title(window_title)
        self.window.geometry("1100x650")

        self.is_running = False
        self.cap = None

        self.notified_known = set()
        self.last_unknown_email_time = 0
        self.start_time = 0
        self.unknown_timer_check = 0

        self.setup_ui()

    def setup_ui(self):
        left_frame = tk.Frame(self.window, width=700, height=650)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(left_frame, width=640, height=480, bg="black")
        self.canvas.pack(padx=10, pady=10)

        btn_frame = tk.Frame(left_frame)
        btn_frame.pack(pady=10)

        self.btn_start = tk.Button(btn_frame, text="Start System", bg="green", fg="white", font=("Arial", 12, "bold"), command=self.start_system)
        self.btn_start.pack(side=tk.LEFT, padx=10)

        self.btn_stop = tk.Button(btn_frame, text="Stop System", bg="red", fg="white", font=("Arial", 12, "bold"), state=tk.DISABLED, command=self.stop_system)
        self.btn_stop.pack(side=tk.LEFT, padx=10)

        right_frame = tk.Frame(self.window, width=400, height=650, bg="#f0f0f0")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=10, pady=10)

        tk.Label(right_frame, text="Trained Faces", font=("Arial", 12, "bold"), bg="#f0f0f0").pack(pady=5)
        
        face_btn_frame = tk.Frame(right_frame, bg="#f0f0f0")
        face_btn_frame.pack(pady=5)
        tk.Button(face_btn_frame, text="Add Face", command=self.add_face).pack(side=tk.LEFT, padx=5)
        tk.Button(face_btn_frame, text="Delete Face", command=self.delete_face).pack(side=tk.LEFT, padx=5)

        self.face_listbox = tk.Listbox(right_frame, width=35, height=8)
        self.face_listbox.pack(pady=5)
        self.update_face_listbox()

        tk.Label(right_frame, text="Registered Emails", font=("Arial", 12, "bold"), bg="#f0f0f0").pack(pady=5)
        
        email_btn_frame = tk.Frame(right_frame, bg="#f0f0f0")
        email_btn_frame.pack(pady=5)
        tk.Button(email_btn_frame, text="Add Email", command=self.add_email).pack(side=tk.LEFT, padx=5)
        tk.Button(email_btn_frame, text="Delete Email", command=self.delete_email).pack(side=tk.LEFT, padx=5)

        self.email_frame = tk.Frame(right_frame, bg="#f0f0f0")
        self.email_frame.pack(pady=5, fill=tk.BOTH)
        
        self.email_vars = {}
        self.refresh_email_checkboxes()

    def update_face_listbox(self):
        self.face_listbox.delete(0, tk.END)
        for name in KNOWN_FACE_NAMES:
            self.face_listbox.insert(tk.END, name)

    def refresh_email_checkboxes(self):
        for widget in self.email_frame.winfo_children():
            widget.destroy()
        self.email_vars.clear()
        
        emails = load_emails()
        for email in emails:
            var = tk.BooleanVar(value=True)
            chk = tk.Checkbutton(self.email_frame, text=email, variable=var, bg="#f0f0f0")
            chk.pack(anchor=tk.W)
            self.email_vars[email] = var

    def add_face(self):
        name = simpledialog.askstring("Input", "Enter Name:")
        if not name:
            return
        
        temp_cap = cv2.VideoCapture(0)
        ret, frame = temp_cap.read()
        temp_cap.release()

        if not ret:
            messagebox.showerror("Error", "Camera failed!")
            return

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        encodings = face_recognition.face_encodings(rgb_frame)

        if len(encodings) > 0:
            KNOWN_FACE_ENCODINGS.append(encodings[0])
            KNOWN_FACE_NAMES.append(name)
            save_faces()
            self.update_face_listbox()
            messagebox.showinfo("Success", f"Face {name} added successfully!")
        else:
            messagebox.showerror("Error", "No face detected. Try again.")

    def delete_face(self):
        selected = self.face_listbox.curselection()
        if not selected:
            messagebox.showwarning("Warning", "Select a face to delete.")
            return
        idx = selected[0]
        name = KNOWN_FACE_NAMES[idx]
        del KNOWN_FACE_NAMES[idx]
        del KNOWN_FACE_ENCODINGS[idx]
        save_faces()
        self.update_face_listbox()
        messagebox.showinfo("Success", f"Face {name} deleted.")

    def add_email(self):
        email = simpledialog.askstring("Input", "Enter Email Address:")
        if email:
            emails = load_emails()
            if email not in emails:
                emails.append(email)
                save_emails_list(emails)
                self.refresh_email_checkboxes()

    def delete_email(self):
        emails = load_emails()
        selected_emails = [e for e, var in self.email_vars.items() if var.get()]
        if not selected_emails:
            messagebox.showwarning("Warning", "Check emails to remove.")
            return
        new_emails = [e for e in emails if e not in selected_emails]
        save_emails_list(new_emails)
        self.refresh_email_checkboxes()

    def speak(self, text):
        def run():
            ENGINE.say(text)
            ENGINE.runAndWait()
        threading.Thread(target=run).start()

    def send_email_alert(self, subject, message, image_path=None):
        selected_emails = [e for e, var in self.email_vars.items() if var.get()]
        if not selected_emails:
            return

        sender_email = "your_email@gmail.com"
        sender_password = "your_app_password"

        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = sender_email
        msg['To'] = ", ".join(selected_emails)

        msg.attach(MIMEText(message, 'plain'))

        if image_path and os.path.exists(image_path):
            with open(image_path, 'rb') as f:
                img_data = f.read()
            img = MIMEImage(img_data, name=os.path.basename(image_path))
            msg.attach(img)

        try:
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, selected_emails, msg.as_string())
            server.quit()
        except Exception as e:
            print(f"Email failed: {e}")

    def start_system(self):
        self.is_running = True
        self.cap = cv2.VideoCapture(0)
        self.btn_start.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.notified_known.clear()
        self.start_time = time.time()
        self.unknown_timer_check = time.time()
        self.update_frame()

    def stop_system(self):
        self.is_running = False
        if self.cap:
            self.cap.release()
        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        self.canvas.delete("all")

    def update_frame(self):
        if not self.is_running:
            return

        ret, frame = self.cap.read()
        if ret:
            current_time = time.time()
            elapsed_time = current_time - self.start_time

            small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
            rgb_small = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

            face_locations = face_recognition.face_locations(rgb_small)
            face_encodings = face_recognition.face_encodings(rgb_small, face_locations)

            face_detected = False

            for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
                face_detected = True
                top *= 4
                right *= 4
                bottom *= 4
                left *= 4

                name = "Unknown"
                if len(KNOWN_FACE_ENCODINGS) > 0:
                    matches = face_recognition.compare_faces(KNOWN_FACE_ENCODINGS, face_encoding, tolerance=0.5)
                    if True in matches:
                        first_match_index = matches.index(True)
                        name = KNOWN_FACE_NAMES[first_match_index]

                cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0) if name != "Unknown" else (0, 0, 255), 2)
                cv2.putText(frame, name, (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2)

                if elapsed_time <= 20:
                    if name != "Unknown":
                        if name not in self.notified_known:
                            self.notified_known.add(name)
                            self.speak(f"いらっしゃいませ {name}さん")
                            img_path = "temp_capture.jpg"
                            cv2.imwrite(img_path, frame)
                            self.send_email_alert("Known Visitor Alert", f"Visitor arrived: {name}", img_path)
                    else:
                        if current_time - self.unknown_timer_check >= 10:
                            self.unknown_timer_check = current_time
                            self.speak("誰さんですか")
                            img_path = "temp_unknown.jpg"
                            cv2.imwrite(img_path, frame)
                            self.send_email_alert("Unknown Visitor Alert", "Unknown person detected!", img_path)
                else:
                    if name != "Unknown":
                        if name not in self.notified_known:
                            self.notified_known.add(name)
                            self.speak(f"いらっしゃいませ {name}さん")
                            img_path = "temp_capture.jpg"
                            cv2.imwrite(img_path, frame)
                            self.send_email_alert("Known Visitor Alert", f"Visitor arrived: {name}", img_path)
                    else:
                        if current_time - self.last_unknown_email_time >= 60:
                            self.last_unknown_email_time = current_time
                            self.speak("誰さんですか")
                            img_path = "temp_unknown.jpg"
                            cv2.imwrite(img_path, frame)
                            self.send_email_alert("Unknown Intruder Alert", "Unknown person detected for 1 minute interval.", img_path)

            photo = PIL.ImageTk.PhotoImage(image=PIL.Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
            self.canvas.image = photo
            self.canvas.create_image(0, 0, image=photo, anchor=tk.NW)

        self.window.after(15, self.update_frame)

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root, "Kamata-sai Smart Security Guard & Receptionist")
    root.mainloop()