import cv2
import threading
import numpy as np
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
from PIL import Image, ImageTk
import time
import json

class serumMeasurementApp:
    def __init__(self, window, window_title):
        self.window = window
        self.window.title(window_title)
              
        self.image = None
        self.processed_image = None
        self.show_edges = tk.BooleanVar(value=True)
        self.roi = [0, 0, 640, 480]  # [x, y, w, h]
        self.drawing_roi = False
        self.upper_edge = None
        self.lower_edge = None
        self.tuning_mode = False
        self.calibrating = False
        self.calibration_start = None
        self.calibration_end = None
        
        self.show_edges = tk.BooleanVar(value=True)
        
        # table to record the result
        self.measurement_history = []
        self.history_table = None
        # Create GUI elements
        self.create_widgets()
        self.load_config()

        try:
            self.cam = cv2.VideoCapture(self.config["camera_index"])  #0 from integrated webcam, 1 from usb webcam
            if not self.cam.isOpened():
                raise Exception("Cannot open camera")
        except Exception as e:
            print(f"Error opening camera: {e}")
            # Handle the error, e.g., display an error message to the user
            messagebox.showerror("Error", "No camera available")
            # Exit the application or take alternative action
            self.window.destroy()
        
        time.sleep(2)  # Give the camera time to warm up   
        self.image_lock = threading.Lock()
        self.current_image = None
        self.processing_thread = threading.Thread(target=self.image_processing_loop)
        self.processing_thread.daemon = True
        self.processing_thread.start()     
        # Start video stream
        self.update_video()

    def image_processing_loop(self):
        while True:
            with self.image_lock:
                self.current_image = self.cam.read()[1]
            time.sleep(0.1)  # Capture at 10 FPS
            
    def create_widgets(self):
        # Main frame
        self.main_frame = ttk.Frame(self.window)
        self.main_frame.pack(padx=10, pady=10)

        # Video frame
        self.video_frame = ttk.Frame(self.main_frame)
        self.video_frame.grid(row=0, column=0, padx=10, pady=10)

        self.canvas = tk.Canvas(self.video_frame, width=640, height=480)
        self.canvas.pack()
        self.canvas.bind("<ButtonPress-1>", self.start_roi)
        self.canvas.bind("<B1-Motion>", self.draw_roi)
        self.canvas.bind("<ButtonRelease-1>", self.end_roi)

        # Control frame
        self.control_frame = ttk.Frame(self.main_frame)
        self.control_frame.grid(row=0, column=1, padx=10, pady=10)

        # ROI label
        self.roi_label = ttk.Label(self.control_frame, text="ROI: Click and drag on image")
        self.roi_label.pack(pady=5)

         # Measure button
        self.measure_button = ttk.Button(self.control_frame, text="Measure serum", command=self.measure_serum)
        self.measure_button.pack(pady=5)

        # Result label
        self.result_label = ttk.Label(self.control_frame, text="")
        self.result_label.pack(pady=5)
        # History table (initially empty)
        self.history_table = None
        self.update_history_table()

        # Tuning button
        self.tuning_button = ttk.Button(self.control_frame, text="Enter Tuning Mode", command=self.toggle_tuning_mode)
        self.tuning_button.pack(pady=5)

        # Tuning frame (initially hidden)
        self.tuning_frame = ttk.Frame(self.main_frame)

        # Update the threshold slider label
        self.threshold_label = ttk.Label(self.tuning_frame, text="Edge Detection Sensitivity:")
        self.threshold_label.pack()
        self.threshold_slider = ttk.Scale(self.tuning_frame, from_=0, to=255, orient=tk.HORIZONTAL, length=200, command=self.on_threshold_change)
        self.threshold_slider.set(50)  # Set a default value appropriate for Canny edge detection
        self.threshold_slider.pack()
            
        # Kernel size slider
        self.kernel_label = ttk.Label(self.tuning_frame, text="Gaussian Blur Kernel Size:")
        self.kernel_label.pack()
        self.kernel_slider = ttk.Scale(self.tuning_frame, from_=1, to=21, orient=tk.HORIZONTAL, length=200, command=self.on_kernel_change)
        self.kernel_slider.set(5)  # Set default value to 5
        self.kernel_slider.pack()
        
        self.show_edges_check = ttk.Checkbutton(self.control_frame, text="Show Live Measurment", variable=self.show_edges, command=self.on_show_edges_change)
        
        self.show_edges_check.pack(pady=5)
        # Apply button
        self.apply_button = ttk.Button(self.tuning_frame, text="Apply", command=self.apply_tuning)
        self.apply_button.pack(pady=5)
        
        #Save Config button
        self.save_config_button = ttk.Button(self.control_frame, text="Save Configuration", command=self.save_config)
        self.save_config_button.pack(pady=5)

    def save_config(self):
        self.config["threshold"]= self.threshold_slider.get()
        self.config["kernel_size"]= self.kernel_slider.get()
        self.config["roi"]=self.roi
        
        with open("serum_config.json", "w") as f:
            json.dump(self.config, f)

    def load_config(self):
        try:
            with open("serum_config.json", "r") as f:
                self.config = json.load(f)

            self.threshold_slider.set(self.config.get("threshold", 128))
            self.kernel_slider.set(self.config.get("kernel_size", 5))
            self.roi = self.config.get("roi", [0, 0, 640, 480])
            self.roi_label.config(text=f"ROI: {self.roi}")
        except FileNotFoundError:
            # If the config file doesn't exist, use default values
            pass
        
            
    def start_roi(self, event):
        if not self.tuning_mode:
            self.roi = [event.x, event.y, 0, 0]
            self.drawing_roi = True

    def draw_roi(self, event):
        if not self.tuning_mode and self.drawing_roi:
            self.roi[2] = event.x - self.roi[0]
            self.roi[3] = event.y - self.roi[1]

    def end_roi(self, event):
        if not self.tuning_mode:
            self.drawing_roi = False
            self.roi[2] = max(event.x - self.roi[0], 1)
            self.roi[3] = max(event.y - self.roi[1], 1)
            self.roi_label.config(text=f"ROI: {self.roi}")
       
    def toggle_tuning_mode(self):
        self.tuning_mode = not self.tuning_mode
        if self.tuning_mode:
            self.tuning_button.config(text="Exit Tuning Mode")
            self.tuning_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=10)
            self.process_image()
        else:
            self.tuning_button.config(text="Enter Tuning Mode")
            self.tuning_frame.grid_forget()

    def apply_tuning(self):
        self.process_image()

    def update_video(self):
        try:
            with self.image_lock:
                if self.current_image is not None:
                    self.image = cv2.cvtColor(self.current_image, cv2.COLOR_BGR2RGB)

            if self.image is not None:
                display_image = self.image.copy()

                if self.tuning_mode:
                    self.process_image()
                    display_image = self.full_processed_image.copy()
                elif self.show_edges.get():
                    self.process_image()  # Process the image when "Show Edges" is checked
                    self.draw_edges(display_image)

                if self.calibrating:
                    if self.calibration_start and self.calibration_end:
                        cv2.line(display_image, self.calibration_start, self.calibration_end, (255, 255, 0), 2)
                    elif self.calibration_start:
                        cv2.circle(display_image, self.calibration_start, 3, (255, 255, 0), -1)

                self.photo = ImageTk.PhotoImage(image=Image.fromarray(display_image))
                self.canvas.create_image(0, 0, image=self.photo, anchor=tk.NW)

                # Draw the ROI rectangle
                self.canvas.create_rectangle(self.roi[0], self.roi[1], 
                                             self.roi[0]+self.roi[2], 
                                             self.roi[1]+self.roi[3], 
                                             outline="red")
        except Exception as e:
            print(f"Error updating video: {e}")

        self.window.after(100, self.update_video)  # Update at 10 FPS
            
    def on_threshold_change(self, value):
        if self.show_edges.get():
            self.process_image()
        
    def on_kernel_change(self, value):
        if self.show_edges.get():
            self.process_image()
            
    def on_show_edges_change(self):
        if self.show_edges.get():
            self.process_image()
    
    def find_edges(self, edge_image):
        h, w = edge_image.shape

        # Find upper serum edge
        for i in range(h):
            if np.sum(edge_image[i]) > 0.1 * w * 255:
                upper_serum = i
                break
        else:
            return None, None, None

        # Find serum-liquid interface
        for i in range(upper_serum + 10, h):
            if np.sum(edge_image[i]) > 0.1 * w * 255:
                serum_liquid_interface = i
                break
        else:
            return None, None, None

        # Find lower liquid edge
        #for i in range(h - 1, serum_liquid_interface, -1):
        for i in range(serum_liquid_interface+40, h):
            if np.sum(edge_image[i]) > 0.1 * w * 255:
                lower_liquid = i
                break
        else:
            return None, None, None

        return upper_serum, serum_liquid_interface, lower_liquid
    
    def process_image(self):
        if self.image is None:
            return

        try:
            x, y, w, h = self.roi
            roi_image = self.image[y:y+h, x:x+w]

            gray = cv2.cvtColor(roi_image, cv2.COLOR_RGB2GRAY)

            kernel_size = int(self.kernel_slider.get())
            if kernel_size % 2 == 0:
                kernel_size += 1

            blurred = cv2.GaussianBlur(gray, (kernel_size, kernel_size), 0)

            low_threshold = int(self.threshold_slider.get())
            high_threshold = low_threshold * 2
            edges = cv2.Canny(blurred, low_threshold, high_threshold)

            self.processed_image = cv2.cvtColor(edges, cv2.COLOR_GRAY2RGB)

            self.full_processed_image = self.image.copy()
            self.full_processed_image[y:y+h, x:x+w] = self.processed_image

            self.upper_serum, self.serum_liquid_interface, self.lower_liquid = self.find_edges(edges)

        except Exception as e:
            print(f"Error processing image: {e}")
            self.processed_image = None
            self.full_processed_image = None
            self.upper_serum, self.serum_liquid_interface, self.lower_liquid = None, None, None


                
    def draw_edges(self, image):
        if image is None or self.upper_serum is None or self.serum_liquid_interface is None or self.lower_liquid is None:
            return

        try:
            x, y, w, h = self.roi

            # Draw upper serum edge
            cv2.line(image, (x, y + self.upper_serum), (x + w, y + self.upper_serum), (0, 255, 0), 2)
            
            # Draw serum-liquid interface
            cv2.line(image, (x, y + self.serum_liquid_interface), (x + w, y + self.serum_liquid_interface), (255, 255, 0), 2)
            
            # Draw lower liquid edge
            cv2.line(image, (x, y + self.lower_liquid), (x + w, y + self.lower_liquid), (0, 0, 255), 2)
            

            # Draw text labels
            font = cv2.FONT_HERSHEY_SIMPLEX
            cv2.putText(image, "Upper serum", (x, y + self.upper_serum - 10), font, 0.5, (0, 255, 0), 1, cv2.LINE_AA)
            cv2.putText(image, "serum-Liquid Interface", (x, y + self.serum_liquid_interface - 10), font, 0.5, (255, 255, 0), 1, cv2.LINE_AA)
            cv2.putText(image, "Lower Liquid", (x, y + self.lower_liquid + 20), font, 0.5, (0, 0, 255), 1, cv2.LINE_AA)

        except Exception as e:
            print(f"Error drawing edges: {e}")
        
    def update_history_table(self):
        if self.history_table:
            self.history_table.destroy()
        
        self.history_table = ttk.Treeview(self.control_frame, columns=('Time', 'serum', 'Total', 'Ratio'), show='headings', height=3)
        self.history_table.heading('Time', text='Time')
        self.history_table.heading('serum', text='serum (px)')
        self.history_table.heading('Total', text='Total (px)')
        self.history_table.heading('Ratio', text='serum Ratio')
        self.history_table.column('Time', width=150)
        self.history_table.column('serum', width=80)
        self.history_table.column('Total', width=80)
        self.history_table.column('Ratio', width=80)
        self.history_table.pack(pady=10)

        for timestamp, serum_thickness_px, total_height_px, serum_ratio in reversed(self.measurement_history):
            self.history_table.insert('', 'end', values=(
                timestamp,
                f"{serum_thickness_px:.2f}",
                f"{total_height_px:.2f}",
                f"{serum_ratio:.2%}"
            ))
            
    def update_measurement_history(self, serum_thickness_px, total_height_px, serum_ratio):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        self.measurement_history.append((timestamp, serum_thickness_px, total_height_px, serum_ratio))
        if len(self.measurement_history) > 3:
            self.measurement_history.pop(0)
        self.update_history_table()
    
    def measure_serum(self):
        self.process_image()
        
        if self.processed_image is None or self.upper_serum is None or self.serum_liquid_interface is None or self.lower_liquid is None:
            self.result_label.config(text="Could not detect all layers")
            return

        serum_thickness_px = self.serum_liquid_interface - self.upper_serum
        total_height_px = self.lower_liquid - self.upper_serum
        
        serum_ratio = serum_thickness_px / total_height_px if total_height_px > 0 else 0

        result_text = f"serum thickness: {serum_thickness_px:.2f} px\n"
        result_text += f"Total height: {total_height_px:.2f} px\n"
        result_text += f"serum ratio: {serum_ratio:.2%}"
        
        self.result_label.config(text=result_text)

        # Update measurement history with new parameters
        self.update_measurement_history(serum_thickness_px, total_height_px, serum_ratio)
        
    
        
if __name__ == "__main__":
    root = tk.Tk()
    app = serumMeasurementApp(root, "Serum Ratio Calculation")
    root.mainloop()