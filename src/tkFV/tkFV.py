import re
import os
import cv2
import glob
import json
import time
import threading
import numpy as np

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageDraw, ImageFont


INIT_FPS = 5  # Default frames per second for playback
INIT_PANE_LAYOUT = "1x1"  # Default pane layout
INIT_BASE_DIR = "" if os.getenv("HOME") is None else os.getenv("HOME")  # Default base directory


class PaneConfig:
    def __init__(self, pattern="", enabled=True):
        self.pattern = pattern
        self.enabled = enabled
        self.files = []


class FileVisualizationSoftware:
    def __init__(self, root):
        self.root = root
        self.root.title("tkFV - regex based file visualizer")
        self.root.geometry("1600x1200")

        # State variables
        self.current_frame = 0
        self.is_playing = False
        self.fps = INIT_FPS
        self.pane_layout = INIT_PANE_LAYOUT
        self.base_directory = INIT_BASE_DIR
        self.pane_configs = {}  # Dictionary to store pane configurations
        self.max_frames = 0

        # Setup GUI
        self.setup_gui()
        self.initialize_panes()

    def setup_gui(self):
        # Create main paned window
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left panel for controls
        left_frame = ttk.Frame(main_paned)
        main_paned.add(left_frame, weight=1)

        # Right panel for visualization
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=3)

        self.setup_control_panel(left_frame)
        self.setup_visualization_panel(right_frame)

        # Status bar
        self.status_var = tk.StringVar(value="Ready - Select base directory to start")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def setup_control_panel(self, parent):
        # Scrollable frame for controls
        canvas = tk.Canvas(parent)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Base directory selection
        dir_frame = ttk.LabelFrame(scrollable_frame, text="Base Directory", padding="10")
        dir_frame.pack(fill=tk.X, padx=5, pady=5)

        self.dir_label = ttk.Label(dir_frame, text="No directory selected", wraplength=300)
        self.dir_label.pack(anchor=tk.W, pady=2)

        ttk.Button(
            dir_frame, text="Select Base Directory", command=self.select_base_directory
        ).pack(pady=5)

        # Layout selection
        layout_frame = ttk.LabelFrame(scrollable_frame, text="Layout Configuration", padding="10")
        layout_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(layout_frame, text="Pane Layout:").pack(anchor=tk.W)
        self.layout_var = tk.StringVar(value=INIT_PANE_LAYOUT)
        layout_combo = ttk.Combobox(
            layout_frame,
            textvariable=self.layout_var,
            values=["1x1", "2x1", "1x2", "2x2", "3x2", "2x3", "3x3", "4x2", "2x4"],
        )
        layout_combo.pack(fill=tk.X, pady=2)
        layout_combo.bind("<<ComboboxSelected>>", self.on_layout_change)

        # Pane configuration area
        self.pane_config_frame = ttk.LabelFrame(
            scrollable_frame, text="Pane Patterns", padding="10"
        )
        self.pane_config_frame.pack(fill=tk.X, padx=5, pady=5)

        # Playback controls
        playback_frame = ttk.LabelFrame(scrollable_frame, text="Playback Controls", padding="10")
        playback_frame.pack(fill=tk.X, padx=5, pady=5)

        # Play/Pause/Stop buttons
        button_frame = ttk.Frame(playback_frame)
        button_frame.pack(fill=tk.X, pady=5)

        self.play_button = ttk.Button(button_frame, text="Play", command=self.toggle_playback)
        self.play_button.pack(side=tk.LEFT, padx=2)

        ttk.Button(button_frame, text="Stop", command=self.stop_playback).pack(side=tk.LEFT, padx=2)

        # FPS control
        fps_frame = ttk.Frame(playback_frame)
        fps_frame.pack(fill=tk.X, pady=5)

        ttk.Label(fps_frame, text="FPS:").pack(side=tk.LEFT)
        self.fps_var = tk.StringVar(value=str(INIT_FPS))
        fps_entry = ttk.Entry(fps_frame, textvariable=self.fps_var, width=8)
        fps_entry.pack(side=tk.LEFT, padx=5)
        fps_entry.bind("<Return>", self.update_fps)

        # Frame control
        ttk.Label(playback_frame, text="Frame Navigation:").pack(anchor=tk.W, pady=(10, 0))
        self.frame_var = tk.IntVar()
        self.frame_scale = ttk.Scale(
            playback_frame,
            from_=0,
            to=0,
            variable=self.frame_var,
            orient=tk.HORIZONTAL,
            command=self.update_frame,
        )
        self.frame_scale.pack(fill=tk.X, pady=2)

        self.frame_label = ttk.Label(playback_frame, text="Frame: 0/0")
        self.frame_label.pack(anchor=tk.W)

        # Action buttons
        action_frame = ttk.LabelFrame(scrollable_frame, text="Actions", padding="10")
        action_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(action_frame, text="Refresh File Lists", command=self.refresh_all_patterns).pack(
            fill=tk.X, pady=2
        )

        ttk.Button(
            action_frame, text="Preview Current Frame", command=self.visualize_current_frame
        ).pack(fill=tk.X, pady=2)

        # Export controls
        export_frame = ttk.LabelFrame(scrollable_frame, text="Export", padding="10")
        export_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(export_frame, text="Export as Video", command=self.export_video).pack(
            fill=tk.X, pady=2
        )
        ttk.Button(export_frame, text="Export Current Frame", command=self.export_frame).pack(
            fill=tk.X, pady=2
        )

        # Configuration save/load
        config_frame = ttk.LabelFrame(scrollable_frame, text="Configuration", padding="10")
        config_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(config_frame, text="Save Configuration", command=self.save_config).pack(
            fill=tk.X, pady=1
        )
        ttk.Button(config_frame, text="Load Configuration", command=self.load_config).pack(
            fill=tk.X, pady=1
        )

    def setup_visualization_panel(self, parent):
        viz_frame = ttk.LabelFrame(parent, text="Visualization", padding="10")
        viz_frame.pack(fill=tk.BOTH, expand=True)

        # Canvas for visualization
        self.canvas = tk.Canvas(viz_frame, bg="black", width=1000, height=700)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Bind canvas resize
        self.canvas.bind("<Configure>", self.on_canvas_resize)

    def on_canvas_resize(self, event):
        # Redraw when canvas is resized
        if hasattr(self, "current_image"):
            self.root.after(100, self.visualize_current_frame)

    def select_base_directory(self):
        directory = filedialog.askdirectory()
        if directory:
            self.base_directory = directory
            self.dir_label.config(text=f"Base: {directory}")
            self.refresh_all_patterns()
            self.update_status(f"Base directory set to: {directory}")

    def initialize_panes(self):
        self.create_pane_widgets()

    def on_layout_change(self, event=None):
        self.create_pane_widgets()
        if self.base_directory:
            self.refresh_all_patterns()

    def create_pane_widgets(self):
        # Clear existing widgets
        for widget in self.pane_config_frame.winfo_children():
            widget.destroy()

        self.pane_configs.clear()

        # Parse layout
        rows, cols = map(int, self.layout_var.get().split("x"))
        total_panes = rows * cols

        # Create configuration widgets for each pane
        for i in range(total_panes):
            pane_frame = ttk.LabelFrame(self.pane_config_frame, text=f"Pane {i+1}", padding="5")
            pane_frame.pack(fill=tk.X, pady=2)

            # Enable checkbox
            enabled_var = tk.BooleanVar(value=True)
            ttk.Checkbutton(pane_frame, text="Enabled", variable=enabled_var).pack(anchor=tk.W)

            # Pattern entry
            ttk.Label(pane_frame, text="File Pattern:").pack(anchor=tk.W)
            pattern_var = tk.StringVar()
            pattern_entry = ttk.Entry(pane_frame, textvariable=pattern_var, width=50)
            pattern_entry.pack(fill=tk.X, pady=2)

            # Helper text
            ttk.Label(
                pane_frame,
                text="Examples: images/*.png, data/frame_*.jpg, logs/log_*.txt",
                font=("TkDefaultFont", 8),
                foreground="gray",
            ).pack(anchor=tk.W)

            # File count label
            count_label = ttk.Label(pane_frame, text="Files: 0", foreground="blue")
            count_label.pack(anchor=tk.W)

            # Browse button
            browse_button = ttk.Button(
                pane_frame, text="Browse Pattern", command=lambda idx=i: self.browse_pattern(idx)
            )
            browse_button.pack(anchor=tk.W, pady=2)

            # Store references
            config = PaneConfig()
            config.enabled_var = enabled_var
            config.pattern_var = pattern_var
            config.count_label = count_label
            config.pattern_entry = pattern_entry

            self.pane_configs[i] = config

            # Bind pattern change
            pattern_var.trace("w", lambda *args, idx=i: self.on_pattern_change(idx))
            enabled_var.trace("w", lambda *args, idx=i: self.on_pattern_change(idx))

    def browse_pattern(self, pane_idx):
        if not self.base_directory:
            messagebox.showwarning("Warning", "Please select a base directory first")
            return

        # Open file dialog starting from base directory
        filetypes = [
            ("Image files", "*.png *.jpg *.jpeg *.gif *.bmp"),
            ("Text files", "*.txt *.log *.csv"),
            ("Code files", "*.py *.js *.html *.css *.json"),
            ("All files", "*.*"),
        ]

        filename = filedialog.askopenfilename(
            initialdir=self.base_directory,
            title=f"Select example file for Pane {pane_idx+1}",
            filetypes=filetypes,
        )

        if filename:
            # Convert absolute path to relative pattern
            rel_path = os.path.relpath(filename, self.base_directory)
            # Create a pattern by replacing the numeric part with a wildcard
            pattern_dir = os.path.dirname(rel_path)
            base_filename = os.path.basename(rel_path)

            # Extract prefix and extension
            file_parts = os.path.splitext(base_filename)
            file_basename = file_parts[0]
            file_ext = file_parts[1]

            # Find the last sequence of digits in the filename
            match = re.search(r"(.+?)(\d+)$", file_basename)
            if match:
                # If the filename has a numeric suffix, replace it with *
                prefix = match.group(1)
                pattern = os.path.join(pattern_dir, f"{prefix}*{file_ext}")
            else:
                # Fallback if no numeric suffix is found
                pattern = os.path.join(pattern_dir, f"{file_basename}*{file_ext}")

            self.pane_configs[pane_idx].pattern_var.set(pattern)

    def extract_numbers(self, filename):
        numbers = re.findall(r"\d+", filename)
        return tuple(map(int, numbers))

    def on_pattern_change(self, pane_idx):
        if not self.base_directory:
            return

        config = self.pane_configs[pane_idx]
        pattern = config.pattern_var.get().strip()

        if pattern and config.enabled_var.get():
            # Resolve pattern relative to base directory
            full_pattern = os.path.join(self.base_directory, pattern)
            try:
                files = sorted(glob.glob(full_pattern), key=self.extract_numbers)
                config.files = files
                config.count_label.config(text=f"Files: {len(files)}")

                if files:
                    config.count_label.config(foreground="green")
                else:
                    config.count_label.config(foreground="red")
            except Exception as e:
                config.files = []
                config.count_label.config(text=f"Error: {str(e)}", foreground="red")
        else:
            config.files = []
            config.count_label.config(text="Files: 0 (disabled)", foreground="gray")

        self.update_max_frames()

    def refresh_all_patterns(self):
        if not self.base_directory:
            return

        for i in self.pane_configs:
            self.on_pattern_change(i)

        self.update_status("All patterns refreshed")

    def update_max_frames(self):
        # Calculate maximum frames needed
        max_files = 0
        for config in self.pane_configs.values():
            if config.enabled_var.get():
                max_files = max(max_files, len(config.files))

        self.max_frames = max_files
        self.frame_scale.config(to=max(0, max_files - 1))
        self.update_frame_label()

    def visualize_current_frame(self):
        if not self.base_directory:
            self.update_status("Please select a base directory first")
            return

        try:
            # Get canvas dimensions
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()

            if canvas_width <= 1 or canvas_height <= 1:
                self.root.after(100, self.visualize_current_frame)
                return

            # Parse layout
            rows, cols = map(int, self.layout_var.get().split("x"))

            # Create main composite image
            composite_img = Image.new("RGB", (canvas_width, canvas_height), "black")

            # Calculate pane dimensions
            pane_width = canvas_width // cols
            pane_height = canvas_height // rows

            # Draw each pane
            for i in range(rows * cols):
                if i not in self.pane_configs:
                    continue

                config = self.pane_configs[i]
                if not config.enabled_var.get():
                    continue

                row = i // cols
                col = i % cols

                x = col * pane_width
                y = row * pane_height

                # Get file for current frame
                if self.current_frame < len(config.files):
                    file_path = config.files[self.current_frame]
                    pane_img = self.create_file_pane(file_path, pane_width, pane_height, i + 1)
                else:
                    pane_img = self.create_empty_pane(pane_width, pane_height, i + 1)

                # Paste the pane image onto the composite
                composite_img.paste(pane_img, (x, y))

            # Convert to PhotoImage and display
            self.current_image = ImageTk.PhotoImage(composite_img)
            self.canvas.delete("all")
            self.canvas.create_image(
                canvas_width // 2, canvas_height // 2, image=self.current_image
            )

        except Exception as e:
            self.update_status(f"Visualization error: {str(e)}")
            print(f"Visualization error: {str(e)}")  # Debug print

    def create_file_pane(self, file_path, width, height, pane_num):
        """Create a PIL Image for a single pane displaying a file"""
        pane_img = Image.new("RGB", (width, height), "black")
        draw = ImageDraw.Draw(pane_img)

        try:
            # Draw border
            draw.rectangle([0, 0, width - 1, height - 1], outline="white")

            # File info
            filename = os.path.basename(file_path)
            file_ext = os.path.splitext(filename)[1].lower()

            # Try to load font
            try:
                font = ImageFont.truetype("arial.ttf", 12)
                small_font = ImageFont.truetype("arial.ttf", 10)
            except:
                font = ImageFont.load_default()
                small_font = ImageFont.load_default()

            # Draw pane number and filename
            header_text = f"P{pane_num}: {filename[:25]}" + ("..." if len(filename) > 25 else "")
            draw.text((5, 5), header_text, fill="yellow", font=font)

            content_y = 25
            content_height = height - 25

            # Handle different file types
            if file_ext in [".jpg", ".jpeg", ".png", ".bmp", ".gif"]:
                self.draw_image_content_on_pane(
                    pane_img, draw, file_path, 0, content_y, width, content_height
                )
            elif file_ext in [
                ".txt",
                ".py",
                ".js",
                ".html",
                ".css",
                ".json",
                ".xml",
                ".log",
                ".csv",
            ]:
                self.draw_text_content(
                    draw, file_path, 0, content_y, width, content_height, small_font
                )
            else:
                self.draw_generic_content(
                    draw, file_path, 0, content_y, width, content_height, font
                )

        except Exception as e:
            draw.text((5, 30), f"Error: {str(e)}", fill="red", font=font)
            print(f"Error in create_file_pane: {str(e)}")  # Debug print

        return pane_img

    def create_empty_pane(self, width, height, pane_num):
        """Create a PIL Image for an empty pane"""
        pane_img = Image.new("RGB", (width, height), "black")
        draw = ImageDraw.Draw(pane_img)

        # Draw border
        draw.rectangle([0, 0, width - 1, height - 1], outline="gray")

        try:
            font = ImageFont.truetype("arial.ttf", 12)
        except:
            font = ImageFont.load_default()

        # Draw pane info
        draw.text((5, 5), f"Pane {pane_num}: No file", fill="gray", font=font)
        draw.text((width // 2 - 30, height // 2), "Empty", fill="gray", font=font)

        return pane_img

    def draw_image_content_on_pane(self, pane_img, draw, file_path, x, y, width, height):
        """Load and draw actual image content onto the pane"""
        try:
            with Image.open(file_path) as img:
                # Convert to RGB if needed (handles RGBA, grayscale, etc.)
                if img.mode != "RGB":
                    img = img.convert("RGB")

                # Calculate scaling to fit within the content area with padding
                content_width = width - 10  # Leave 5px padding on each side
                content_height = height - 30  # Leave space for image info text

                # Calculate aspect ratio preserving dimensions
                img_ratio = img.width / img.height
                content_ratio = content_width / content_height

                if img_ratio > content_ratio:
                    # Image is wider than content area
                    new_width = content_width
                    new_height = int(content_width / img_ratio)
                else:
                    # Image is taller than content area
                    new_height = content_height
                    new_width = int(content_height * img_ratio)

                # Resize the image
                img_resized = img.resize((new_width, new_height), Image.BILINEAR)

                # Calculate centering position
                paste_x = x + (width - new_width) // 2
                paste_y = y + (height - new_height - 20) // 2  # Extra space for info text

                # Paste the actual image onto the pane
                pane_img.paste(img_resized, (paste_x, paste_y))

                # Draw image info at the bottom
                try:
                    info_font = ImageFont.truetype("arial.ttf", 10)
                except:
                    info_font = ImageFont.load_default()

                info_text = f"Image: {img.width}x{img.height} -> {new_width}x{new_height}"
                draw.text((x + 5, y + height - 15), info_text, fill="cyan", font=info_font)

        except Exception as e:
            # If image loading fails, draw error message
            draw.text((x + 5, y + 10), f"Image load error: {str(e)}", fill="red")
            print(f"Image loading error for {file_path}: {str(e)}")

    def draw_text_content(self, draw, file_path, x, y, width, height, font):
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read(800)  # First 800 characters

            # Split into lines
            lines = content.split("\n")
            y_offset = 5
            line_height = 12
            max_lines = (height - 30) // line_height

            for line in lines[:max_lines]:
                if y_offset + line_height > height - 25:
                    break

                # Truncate long lines
                max_chars = (width - 10) // 6  # Rough character width estimation
                if len(line) > max_chars:
                    line = line[: max_chars - 3] + "..."

                draw.text((x + 5, y + y_offset), line, fill="lightgreen", font=font)
                y_offset += line_height

            # File stats
            file_size = os.path.getsize(file_path)
            size_text = f"Size: {file_size} bytes"
            draw.text((x + 5, y + height - 15), size_text, fill="gray", font=font)

        except Exception as e:
            draw.text((x + 5, y + 10), f"Text error: {str(e)}", fill="red", font=font)

    def draw_generic_content(self, draw, file_path, x, y, width, height, font):
        try:
            # File statistics
            stat = os.stat(file_path)
            size = stat.st_size
            modified = time.ctime(stat.st_mtime)

            # Draw file icon
            icon_size = min(32, width // 3, height // 3)
            icon_x = x + width // 2 - icon_size // 2
            icon_y = y + 20
            draw.rectangle(
                [icon_x, icon_y, icon_x + icon_size, icon_y + icon_size],
                outline="white",
                fill="darkgray",
            )

            # File info
            info_lines = [
                f"Size: {size:,} bytes",
                f"Modified: {modified.split()[1]} {modified.split()[2]}",
                f"Type: {os.path.splitext(file_path)[1] or 'No extension'}",
            ]

            y_offset = icon_y + icon_size + 20
            for line in info_lines:
                if y_offset > y + height - 20:
                    break
                draw.text((x + 5, y_offset), line, fill="lightgray", font=font)
                y_offset += 15

        except Exception as e:
            draw.text((x + 5, y + 10), f"File error: {str(e)}", fill="red", font=font)

    def toggle_playback(self):
        if self.is_playing:
            self.stop_playback()
        else:
            self.start_playback()

    def start_playback(self):
        if self.max_frames == 0:
            messagebox.showwarning("Warning", "No files to play")
            return

        self.is_playing = True
        self.play_button.config(text="Pause")
        self.playback_thread = threading.Thread(target=self.playback_loop)
        self.playback_thread.daemon = True
        self.playback_thread.start()

    def stop_playback(self):
        self.is_playing = False
        self.play_button.config(text="Play")

    def playback_loop(self):
        while self.is_playing and self.max_frames > 0:
            try:
                fps = float(self.fps_var.get())
                delay = 1.0 / fps
            except ValueError:
                delay = 0.5

            self.root.after(0, self.next_frame)
            time.sleep(delay)

    def next_frame(self):
        if self.max_frames == 0:
            return

        self.current_frame = (self.current_frame + 1) % self.max_frames
        self.frame_var.set(self.current_frame)
        self.update_frame_label()
        self.visualize_current_frame()

    def update_frame(self, value=None):
        self.current_frame = int(float(value or self.frame_var.get()))
        self.update_frame_label()
        self.visualize_current_frame()

    def update_frame_label(self):
        self.frame_label.config(text=f"Frame: {self.current_frame+1}/{max(1, self.max_frames)}")

    def update_fps(self, event=None):
        try:
            self.fps = float(self.fps_var.get())
        except ValueError:
            self.fps_var.set(str(INIT_FPS))
            self.fps = INIT_FPS

    def save_config(self):
        config_data = {
            "base_directory": self.base_directory,
            "layout": self.layout_var.get(),
            "fps": self.fps_var.get(),
            "panes": {},
        }

        for i, config in self.pane_configs.items():
            config_data["panes"][i] = {
                "pattern": config.pattern_var.get(),
                "enabled": config.enabled_var.get(),
            }

        filename = filedialog.asksaveasfilename(
            defaultextension=".json", filetypes=[("JSON files", "*.json")]
        )

        if filename:
            try:
                with open(filename, "w") as f:
                    json.dump(config_data, f, indent=2)
                self.update_status(f"Configuration saved to {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save configuration: {str(e)}")

    def load_config(self):
        filename = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])

        if filename:
            try:
                with open(filename, "r") as f:
                    config_data = json.load(f)

                # Load base settings
                if "base_directory" in config_data:
                    self.base_directory = config_data["base_directory"]
                    self.dir_label.config(text=f"Base: {self.base_directory}")

                if "layout" in config_data:
                    self.layout_var.set(config_data["layout"])
                    self.create_pane_widgets()

                if "fps" in config_data:
                    self.fps_var.set(config_data["fps"])

                # Load pane configurations
                if "panes" in config_data:
                    for pane_id, pane_data in config_data["panes"].items():
                        pane_idx = int(pane_id)
                        if pane_idx in self.pane_configs:
                            if "pattern" in pane_data:
                                self.pane_configs[pane_idx].pattern_var.set(pane_data["pattern"])
                            if "enabled" in pane_data:
                                self.pane_configs[pane_idx].enabled_var.set(pane_data["enabled"])

                self.refresh_all_patterns()
                self.update_status(f"Configuration loaded from {filename}")

            except Exception as e:
                messagebox.showerror("Error", f"Failed to load configuration: {str(e)}")

    def export_video(self):
        if self.max_frames == 0:
            messagebox.showwarning("Warning", "No frames to export")
            return

        output_path = filedialog.asksaveasfilename(
            defaultextension=".mp4", filetypes=[("MP4 files", "*.mp4"), ("AVI files", "*.avi")]
        )

        if output_path:
            # Run export in separate thread
            export_thread = threading.Thread(target=self.export_video_worker, args=(output_path,))
            export_thread.daemon = True
            export_thread.start()

    def export_video_worker(self, output_path):
        try:
            self.update_status("Exporting video...")

            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            fps = float(self.fps_var.get())

            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            out = cv2.VideoWriter(output_path, fourcc, fps, (canvas_width, canvas_height))

            for frame_idx in range(self.max_frames):
                # Generate frame
                img = Image.new("RGB", (canvas_width, canvas_height), "black")
                draw = ImageDraw.Draw(img)

                rows, cols = map(int, self.layout_var.get().split("x"))
                pane_width = canvas_width // cols
                pane_height = canvas_height // rows

                for i in range(rows * cols):
                    if i not in self.pane_configs:
                        continue

                    config = self.pane_configs[i]
                    if not config.enabled_var.get():
                        continue

                    row = i // cols
                    col = i % cols
                    x = col * pane_width
                    y = row * pane_height

                    if frame_idx < len(config.files):
                        file_path = config.files[frame_idx]
                        self.draw_file_pane(draw, file_path, x, y, pane_width, pane_height, i + 1)
                    else:
                        self.draw_empty_pane(draw, x, y, pane_width, pane_height, i + 1)

                # Convert PIL image to OpenCV format
                cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
                out.write(cv_img)

                self.update_status(f"Exporting frame {frame_idx+1}/{self.max_frames}")

            out.release()
            self.update_status(f"Video exported to {output_path}")
            messagebox.showinfo("Success", f"Video exported successfully to {output_path}")

        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export video: {str(e)}")
            self.update_status("Export failed")

    def export_frame(self):
        if self.max_frames == 0:
            messagebox.showwarning("Warning", "No frames to export")
            return

        output_path = filedialog.asksaveasfilename(
            defaultextension=".png", filetypes=[("PNG files", "*.png"), ("JPEG files", "*.jpg")]
        )

        if output_path:
            try:
                canvas_width = self.canvas.winfo_width()
                canvas_height = self.canvas.winfo_height()

                img = Image.new("RGB", (canvas_width, canvas_height), "black")
                draw = ImageDraw.Draw(img)

                rows, cols = map(int, self.layout_var.get().split("x"))
                pane_width = canvas_width // cols
                pane_height = canvas_height // rows

                for i in range(rows * cols):
                    if i not in self.pane_configs:
                        continue

                    config = self.pane_configs[i]
                    if not config.enabled_var.get():
                        continue

                    row = i // cols
                    col = i % cols
                    x = col * pane_width
                    y = row * pane_height

                    if self.current_frame < len(config.files):
                        file_path = config.files[self.current_frame]
                        self.draw_file_pane(draw, file_path, x, y, pane_width, pane_height, i + 1)
                    else:
                        self.draw_empty_pane(draw, x, y, pane_width, pane_height, i + 1)

                img.save(output_path)
                self.update_status(f"Frame exported to {output_path}")
                messagebox.showinfo("Success", f"Frame exported successfully to {output_path}")

            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export frame: {str(e)}")

    def update_status(self, message):
        self.status_var.set(message)
        self.root.update_idletasks()


def main():
    root = tk.Tk()
    app = FileVisualizationSoftware(root)
    root.mainloop()


if __name__ == "__main__":
    main()
