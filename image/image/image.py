import os
import subprocess
import tempfile
from pathlib import Path
from io import BytesIO

def ensure_executable(models_path):
    executable_path = models_path.parent / 'realesrgan-ncnn-vulkan'
    if not executable_path.exists():
        raise FileNotFoundError(f"Executable not found at {executable_path}")
    os.chmod(executable_path, 0o755)

def list_models(models_path):
    models = [f.stem for f in models_path.glob('*.bin')]
    return models

def enhance_image(input_data, output_path, model='realesr-animevideov3-x4', scale=2, fmt='png'):
    with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{fmt}') as temp_input:
        if isinstance(input_data, bytes):
            temp_input.write(input_data)
        elif isinstance(input_data, BytesIO):
            temp_input.write(input_data.getvalue())
        else:
            with open(input_data, 'rb') as f:
                temp_input.write(f.read())
        temp_input_path = temp_input.name

    executable_path = Path(output_path).parent.parent / 'realesrgan-ncnn-vulkan'
    command = [
        str(executable_path),
        '-i', temp_input_path,
        '-o', output_path,
        '-n', model,
        '-s', str(scale),
        '-f', fmt
    ]
    try:
        subprocess.run(command, check=True)
    finally:
        os.unlink(temp_input_path)

def enhance_anime_video(input_video, output_video, model='realesr-animevideov3-x2', scale=2):
    tmp_frames = 'tmp_frames'
    out_frames = 'out_frames'
    
    os.makedirs(tmp_frames, exist_ok=True)
    os.makedirs(out_frames, exist_ok=True)

    extract_frames_command = [
        'ffmpeg', '-i', input_video, '-qscale:v', '1', '-qmin', '1', '-qmax', '1', '-vsync', '0',
        os.path.join(tmp_frames, 'frame%08d.jpg')
    ]
    subprocess.run(extract_frames_command, check=True)

    enhance_frames_command = [
        './realesrgan-ncnn-vulkan',
        '-i', tmp_frames,
        '-o', out_frames,
        '-n', model,
        '-s', str(scale),
        '-f', 'jpg'
    ]
    subprocess.run(enhance_frames_command, check=True)

    merge_frames_command = [
        'ffmpeg', '-i', os.path.join(out_frames, 'frame%08d.jpg'), '-i', input_video,
        '-map', '0:v:0', '-map', '1:a:0', '-c:a', 'copy', '-c:v', 'libx264', '-r', '23.98', '-pix_fmt', 'yuv420p',
        output_video
    ]
    subprocess.run(merge_frames_command, check=True)

def upscale_small_files(conn, small_files):
    ensure_executable()
    chosen_model = 'realesrgan-x4plus'

    # Optionally, upload the upscaled image back to NAS
    upload_choice = input(f"Do you want to upload files back to NAS? (yes/no): ").strip().lower()

    for file in small_files:
        nas_path = file['path']
        file_name, file_extension = os.path.splitext(os.path.basename(nas_path))
        output_file_name = f"{file_name}_upscaled{file_extension}"
        
        if file_extension.lower() in ['.jpg', '.jpeg', '.png']:
            # Create a temporary directory to store the downloaded and upscaled files
            with tempfile.TemporaryDirectory() as temp_dir:
                # Download the file from NAS to a temporary local file
                local_input_path = os.path.join(temp_dir, os.path.basename(nas_path))
                with open(local_input_path, 'wb') as f:
                    conn.retrieveFile('home', nas_path, f)

                # Set the local output path
                local_output_path = os.path.join(temp_dir, output_file_name)

                # Upscale the image
                enhance_image(local_input_path, local_output_path, chosen_model, scale=4, fmt=file_extension.lstrip('.'))

                print(f"Upscaled {nas_path} to {local_output_path}")

                # Optionally, upload the upscaled image back to NAS
                if upload_choice == 'yes':
                    nas_output_path = os.path.join(os.path.dirname(nas_path), output_file_name)
                    with open(local_output_path, 'rb') as f:
                        conn.storeFile('home', nas_output_path, f)
                    print(f"Uploaded {local_output_path} to NAS as {nas_output_path}")

            # The temporary directory and its contents are automatically cleaned up when the context manager exits
        else:
            print(f"Skipping {nas_path}: not a supported image format")
