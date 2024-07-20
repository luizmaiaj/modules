import os
import subprocess
import tempfile
from typing import List, Tuple
from multiprocessing import Pool, cpu_count
from pathlib import Path
from io import BytesIO

def enhance_single_image(args):
    executable_path, input_path, output_path, model, scale, fmt = args
    command = [
        str(executable_path),
        '-i', input_path,
        '-o', output_path,
        '-n', model,
        '-s', str(scale),
        '-f', fmt
    ]
    try:
        subprocess.run(command, check=True)
        return (input_path, output_path, True)
    except subprocess.CalledProcessError as e:
        print(f"Error enhancing {input_path}: {e}")
        return (input_path, output_path, False)
    except Exception as e:
        print(f"Unexpected error enhancing {input_path}: {e}")
        return (input_path, output_path, False)

def enhance_multiple_images_parallel(
    executable_path: str,
    input_files: List[str],
    appendix: str = "_enhanced",
    model: str = 'realesr-animevideov3-x4',
    scale: int = 2,
    fmt: str = 'png',
    num_processes: int = None
) -> List[Tuple[str, str]]:
    """
    Enhance multiple images in parallel and save them in the same folder as the input files.

    Args:
    executable_path (str): Path to the image enhancement executable.
    input_files (List[str]): List of paths to input image files.
    appendix (str): String to append to the filename of enhanced images.
    model (str): Name of the model to use for enhancement.
    scale (int): Scale factor for image enhancement.
    fmt (str): Output format for enhanced images.
    num_processes (int): Number of processes to use. If None, uses the number of CPU cores.

    Returns:
    List[Tuple[str, str]]: List of tuples containing (input_path, output_path) for each successfully processed file.
    """
    if num_processes is None:
        num_processes = cpu_count()

    # Prepare arguments for each file
    args_list = []
    for input_path in input_files:
        dir_name, file_name = os.path.split(input_path)
        file_name_without_ext, file_ext = os.path.splitext(file_name)
        output_file_name = f"{file_name_without_ext}{appendix}{file_ext}"
        output_path = os.path.join(dir_name, output_file_name)
        args_list.append((executable_path, input_path, output_path, model, scale, fmt))

    # Process images in parallel
    with Pool(processes=num_processes) as pool:
        results = pool.map(enhance_single_image, args_list)

    # Filter and return successful enhancements
    enhanced_files = [(input_path, output_path) for input_path, output_path, success in results if success]
    
    print(f"Successfully enhanced {len(enhanced_files)} out of {len(input_files)} images.")
    return enhanced_files

def ensure_executable(models_path):
    executable_path = models_path.parent / 'realesrgan-ncnn-vulkan'
    if not executable_path.exists():
        raise FileNotFoundError(f"Executable not found at {executable_path}")
    os.chmod(executable_path, 0o755)

def list_models(models_path):
    models = [f.stem for f in models_path.glob('*.bin')]
    return models

def enhance_image(executable_path, input_path, output_path, model='realesr-animevideov3-x4', scale=2, fmt='png'):
    command = [
        str(executable_path),
        '-i', input_path,
        '-o', output_path,
        '-n', model,
        '-s', str(scale),
        '-f', fmt
    ]
    try:
        subprocess.run(command, check=True)
    except ValueError as e:
        print(e)

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
