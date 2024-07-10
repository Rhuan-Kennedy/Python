import os
import random
import subprocess
import threading
import multiprocessing
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

def get_folder_path(prompt):
    folder_path = filedialog.askdirectory(title=prompt)
    return folder_path.strip() if folder_path else None

def get_file_path(prompt, filetypes):
    file_path = filedialog.askopenfilename(title=prompt, filetypes=filetypes)
    return file_path.strip() if file_path else None

def list_files(path, extensions):
    return [os.path.join(path, f) for f in os.listdir(path) if f.endswith(extensions)]

def apply_filter(filter_name):
    if filter_name == "random":
        brightness = random.uniform(-0.01, 0.10)
        contrast = random.uniform(0.99, 1.01)
        rs = random.uniform(-0.01, 0.10)
        gs = random.uniform(-0.01, 0.10)
        bs = random.uniform(-0.01, 0.10)
        sigma = random.uniform(0.0, 0.10)
        filter_complex = f'eq=brightness={brightness}:contrast={contrast},'
        filter_complex += f'colorbalance=rs={rs}:gs={gs}:bs={bs},'
        filter_complex += f'gblur=sigma={sigma}'
        return filter_complex
    elif filter_name == "slight_sepia":
        return "colorchannelmixer=.393:.769:.189:.349:.686:.168:.272:.534:.131"
    elif filter_name == "slight_brightness":
        return "eq=brightness=0.01"
    elif filter_name == "slight_blur":
        return "gblur=sigma=0.1"
    else:
        return ""

def get_video_resolution(video_path, ffmpeg_path):
    try:
        result = subprocess.run([ffmpeg_path, '-i', video_path], stderr=subprocess.PIPE, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        for line in result.stderr.split('\n'):
            if "Stream #0:0" in line and "Video:" in line:
                parts = line.split(',')
                for part in parts:
                    if 'x' in part and 'Video:' not in part:
                        resolution = part.strip().split(' ')[0]
                        width, height = map(int, resolution.split('x'))
                        return width, height
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg command failed with error: {e.stderr}")
    return None, None

def get_video_duration(video_path, ffmpeg_path):
    try:
        result = subprocess.run([ffmpeg_path, '-i', video_path], stderr=subprocess.PIPE, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        for line in result.stderr.split('\n'):
            if "Duration" in line:
                duration = line.split("Duration: ")[1].split(",")[0]
                h, m, s = duration.split(":")
                total_seconds = int(h) * 3600 + int(m) * 60 + float(s)
                return total_seconds
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg command failed with error: {e.stderr}")
    return None

def process_video(video_file, music_files, video_path, save_path, ffmpeg_path, color_filter, image_path, progress_queue):
    video_full_path = os.path.join(video_path, video_file)
    if not os.path.exists(video_full_path):
        progress_queue.put(f"Video file not found: {video_full_path}")
        return

    video_width, video_height = get_video_resolution(video_full_path, ffmpeg_path)
    if video_width is None or video_height is None:
        progress_queue.put("Could not determine video resolution. Skipping video.")
        return

    video_duration = get_video_duration(video_full_path, ffmpeg_path)
    if video_duration is None:
        progress_queue.put("Could not determine video duration. Skipping video.")
        return

    music_file = random.choice(music_files)
    volume_music = 0.001

    output_file = os.path.join(save_path, f"Edited_{os.path.basename(video_file)}")

    if image_path:
        image_duration = 5  # Duration for which the image will be shown at the end
        filter_complex = f"[0:v]scale={video_width}:{video_height},setsar=1:1,format=yuv420p,{color_filter}[v];"
        filter_complex += f"[1:a]volume={volume_music},atrim=duration={video_duration}[music];"
        filter_complex += f"[0:a][music]amix=inputs=2:duration=first:dropout_transition=3[a];"
        filter_complex += f"[2:v]scale={video_width}:{video_height},setsar=1:1,format=yuv420p,trim=duration={image_duration},setpts=PTS-STARTPTS[image];"
        filter_complex += f"[v][image]concat=n=2:v=1:a=0[outv]"
        cmd = [
            ffmpeg_path,
            '-i', video_full_path,
            '-i', music_file,
            '-loop', '1', '-t', str(image_duration), '-i', image_path,
            '-filter_complex', filter_complex,
            '-map', '[outv]',
            '-map', '[a]',
            '-c:v', 'libx264',
            '-b:v', '2000k',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-strict', 'experimental',
            '-preset', 'ultrafast',
            '-pix_fmt', 'yuv420p',
            output_file
        ]
    else:
        filter_complex = f"[0:v]scale={video_width}:{video_height},setsar=1:1,format=yuv420p,{color_filter}[v];"
        filter_complex += f"[1:a]volume={volume_music},atrim=duration={video_duration}[music];"
        filter_complex += f"[0:a][music]amix=inputs=2:duration=first:dropout_transition=3[a]"
        cmd = [
            ffmpeg_path,
            '-i', video_full_path,
            '-i', music_file,
            '-filter_complex', filter_complex,
            '-map', '[v]',
            '-map', '[a]',
            '-c:v', 'libx264',
            '-b:v', '2000k',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-strict', 'experimental',
            '-preset', 'ultrafast',
            '-pix_fmt', 'yuv420p',
            output_file
        ]

    try:
        result = subprocess.run(cmd, check=True, text=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
        progress_queue.put(f"Edited video saved at: {output_file}")
    except subprocess.CalledProcessError as e:
        progress_queue.put(f"FFmpeg command failed with error: {e.stderr}")
    except FileNotFoundError:
        progress_queue.put("FFmpeg executable not found.")
    except Exception as e:
        progress_queue.put(f"An unexpected error occurred: {e}")

def get_ffmpeg_path():
    ffmpeg_path = filedialog.askopenfilename(title="Selecione o executável do FFmpeg", filetypes=[("FFmpeg", "ffmpeg.exe")])
    if not ffmpeg_path:
        print("FFmpeg executável não selecionado. Saindo.")
        exit()
    return ffmpeg_path

def start_processing_thread(video_path, music_path, save_path, image_path, ffmpeg_path, progress_bar, progress_label, start_button, progress_indicator):
    music_files = list_files(music_path, ('.mp3', '.wav'))
    if not music_files:
        messagebox.showerror("Error", "Nenhum arquivo de música encontrado.")
        return

    video_files = list_files(video_path, ('.mp4', '.avi', '.mov'))
    if not video_files:
        messagebox.showerror("Error", "Nenhum arquivo de vídeo encontrado.")
        return

    progress_bar['maximum'] = len(video_files)
    progress_bar['value'] = 0
    start_button.config(state=tk.DISABLED)
    progress_indicator.start()

    progress_queue = multiprocessing.Queue()

    def update_progress():
        while True:
            try:
                message = progress_queue.get(timeout=1)
                if "Edited video saved at" in message:
                    progress_bar.step(1)
                progress_label.config(text=message)
            except:
                if progress_queue.empty():
                    break

    def process_all_videos():
        processes = []
        max_processes = 4  # Adjust based on your CPU capabilities
        for video_file in video_files:
            p = multiprocessing.Process(target=process_video, args=(video_file, music_files, video_path, save_path, ffmpeg_path, apply_filter("random"), image_path, progress_queue))
            processes.append(p)
            if len(processes) >= max_processes:
                for proc in processes:
                    proc.start()
                for proc in processes:
                    proc.join()
                processes = []
        if processes:
            for proc in processes:
                proc.start()
            for proc in processes:
                proc.join()

        progress_indicator.stop()
        start_button.config(state=tk.NORMAL)
        messagebox.showinfo("Success", "Todos os vídeos foram processados com sucesso.")

    threading.Thread(target=update_progress).start()
    threading.Thread(target=process_all_videos).start()

def main_gui():
    root = tk.Tk()
    root.title("Video Processing")

    def on_closing():
        if messagebox.askokcancel("Quit", "Você quer sair do programa?"):
            root.destroy()
            os._exit(0)

    root.protocol("WM_DELETE_WINDOW", on_closing)

    def select_video_path():
        path = filedialog.askdirectory(title="Por favor, selecione a pasta que contém os vídeos:")
        if path:
            video_path_entry.delete(0, tk.END)
            video_path_entry.insert(0, path)

    def select_music_path():
        path = filedialog.askdirectory(title="Por favor, selecione a pasta que contém as músicas:")
        if path:
            music_path_entry.delete(0, tk.END)
            music_path_entry.insert(0, path)

    def select_save_path():
        path = filedialog.askdirectory(title="Por favor, selecione a pasta onde os vídeos editados serão salvos:")
        if path:
            save_path_entry.delete(0, tk.END)
            save_path_entry.insert(0, path)

    def select_image_path():
        path = filedialog.askopenfilename(title="Por favor, selecione a imagem para adicionar ao vídeo:", filetypes=[("Image files", "*.png;*.jpg;*.jpeg")])
        if path:
            image_path_entry.delete(0, tk.END)
            image_path_entry.insert(0, path)

    def start_processing():
        video_path = video_path_entry.get()
        music_path = music_path_entry.get()
        save_path = save_path_entry.get()
        image_path = image_path_entry.get()
        ffmpeg_path = get_ffmpeg_path()

        if not all([video_path, music_path, save_path, ffmpeg_path]):
            messagebox.showerror("Error", "Um ou mais inputs estão vazios.")
            return

        threading.Thread(target=start_processing_thread, args=(video_path, music_path, save_path, image_path, ffmpeg_path, progress_bar, progress_label, start_button, progress_indicator)).start()
        progress_indicator.start()

    # Video path
    video_path_label = tk.Label(root, text="Video Path:")
    video_path_label.grid(row=0, column=0, padx=10, pady=10)
    video_path_entry = tk.Entry(root, width=50)
    video_path_entry.grid(row=0, column=1, padx=10, pady=10)
    video_path_button = tk.Button(root, text="Browse", command=select_video_path)
    video_path_button.grid(row=0, column=2, padx=10, pady=10)

    # Music path
    music_path_label = tk.Label(root, text="Music Path:")
    music_path_label.grid(row=1, column=0, padx=10, pady=10)
    music_path_entry = tk.Entry(root, width=50)
    music_path_entry.grid(row=1, column=1, padx=10, pady=10)
    music_path_button = tk.Button(root, text="Browse", command=select_music_path)
    music_path_button.grid(row=1, column=2, padx=10, pady=10)

    # Save path
    save_path_label = tk.Label(root, text="Save Path:")
    save_path_label.grid(row=2, column=0, padx=10, pady=10)
    save_path_entry = tk.Entry(root, width=50)
    save_path_entry.grid(row=2, column=1, padx=10, pady=10)
    save_path_button = tk.Button(root, text="Browse", command=select_save_path)
    save_path_button.grid(row=2, column=2, padx=10, pady=10)

    # Image path
    image_path_label = tk.Label(root, text="Image Path:")
    image_path_label.grid(row=3, column=0, padx=10, pady=10)
    image_path_entry = tk.Entry(root, width=50)
    image_path_entry.grid(row=3, column=1, padx=10, pady=10)
    image_path_button = tk.Button(root, text="Browse", command=select_image_path)
    image_path_button.grid(row=3, column=2, padx=10, pady=10)

    # Progress bar
    progress_bar = ttk.Progressbar(root, orient="horizontal", length=400, mode="determinate")
    progress_bar.grid(row=4, column=0, columnspan=3, padx=10, pady=20)

    # Progress label
    progress_label = tk.Label(root, text="Progress:")
    progress_label.grid(row=5, column=0, columnspan=3, padx=10, pady=10)

    # Progress indicator
    progress_indicator = ttk.Progressbar(root, orient="horizontal", mode="indeterminate")
    progress_indicator.grid(row=6, column=0, columnspan=3, padx=10, pady=10)

    # Start button
    start_button = tk.Button(root, text="Start Processing", command=start_processing)
    start_button.grid(row=7, column=0, columnspan=3, padx=10, pady=10)

    root.mainloop()

if __name__ == '__main__':
    multiprocessing.freeze_support()
    main_gui()
