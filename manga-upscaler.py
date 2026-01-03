#!/usr/bin/env python3

import os
import sys
import subprocess
import argparse
from pathlib import Path
import urllib.request
import zipfile
import platform
import shutil
import re

VENV_DIR = Path(__file__).parent / "venv"
MODELS_DIR = Path(__file__).parent / "models"
BIN_DIR = Path(__file__).parent / "bin"

AVAILABLE_MODELS = {
    "waifu2x": {
        "type": "ncnn",
        "scale": 2,
        "description": "Waifu2x x2 (fast, line-art focused)",
        "requires_venv": False,
        "requires_binary": True,
        "binary_name": "waifu2x-ncnn-vulkan",
        "binary_url": {
            "Windows": "https://github.com/nihui/waifu2x-ncnn-vulkan/releases/download/20220728/waifu2x-ncnn-vulkan-20220728-windows.zip",
            "Linux": "https://github.com/nihui/waifu2x-ncnn-vulkan/releases/download/20220728/waifu2x-ncnn-vulkan-20220728-ubuntu.zip",
            "Darwin": "https://github.com/nihui/waifu2x-ncnn-vulkan/releases/download/20220728/waifu2x-ncnn-vulkan-20220728-macos.zip"
        },
        "models_dir": MODELS_DIR / "waifu2x",
        "models_subdir": "models-cunet",
        "quality_settings": {
            "denoise_level": {
                "type": "int",
                "default": 0,
                "min": -1,
                "max": 3,
                "description": "Denoise level (-1=none, 0=low, 1-3=higher)"
            },
            "tile_size": {
                "type": "int",
                "default": 0,
                "min": 0,
                "max": 2048,
                "description": "Tile size for processing (0=auto, 32-2048 for manual)"
            },
            "gpu_id": {
                "type": "int",
                "default": 0,
                "min": 0,
                "max": 16,
                "description": "GPU device to use (0=default GPU)"
            }
        }
    }
}

QUALITY_PRESETS = {
    "waifu2x": {
        "fast": {"denoise_level": -1, "tile_size": 400},
        "balanced": {"denoise_level": 0, "tile_size": 0},
        "quality": {"denoise_level": 2, "tile_size": 200}
    }
}

class ModelError(Exception):
    pass

class EnvironmentError(Exception):
    pass

class DownloadProgressBar:
    def __init__(self):
        self.pbar = None

    def __call__(self, block_num, block_size, total_size):
        if not self.pbar:
            self.pbar = True
            print(f"   Total size: {total_size / (1024*1024):.1f} MB")
        
        downloaded = block_num * block_size
        if total_size > 0:
            percent = min(downloaded * 100 / total_size, 100)
            bar_length = 50
            filled_length = int(bar_length * downloaded // total_size)
            bar = '█' * filled_length + '░' * (bar_length - filled_length)
            print(f'\r   [{bar}] {percent:.1f}%', end='', flush=True)
            
            if downloaded >= total_size:
                print()

class ProgressTracker:
    def __init__(self, total_items, description="Processing"):
        self.total_items = total_items
        self.current_item = 0
        self.description = description
        self.bar_length = 50
        self._display(None)
        
    def update(self, item_name=None):
        self.current_item += 1
        self._display(item_name)
    
    def _display(self, item_name=None):
        if self.total_items == 0:
            return
            
        percent = (self.current_item / self.total_items) * 100
        filled_length = int(self.bar_length * self.current_item // self.total_items)
        bar = '█' * filled_length + '░' * (self.bar_length - filled_length)
        
        status = f"[{self.current_item}/{self.total_items}]"
        if item_name:
            if len(item_name) > 40:
                item_name = item_name[:37] + "..."
            status += f" {item_name}"
        
        print(f'\r   [{bar}] {percent:.1f}% {status}', end='', flush=True)
        
        if self.current_item >= self.total_items:
            print()
    
    def finish(self):
        if self.current_item < self.total_items:
            self.current_item = self.total_items
            self._display()
        print()

def get_venv_python():
    if os.name == 'nt':
        return VENV_DIR / "Scripts" / "python.exe"
    else:
        return VENV_DIR / "bin" / "python"

def detect_vulkan_gpus():
    system = platform.system()
    gpus = []
    
    try:
        if system == "Windows":
            result = subprocess.run(
                ["vulkaninfo"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                gpu_id = 0
                for line in lines:
                    if 'deviceName' in line:
                        match = re.search(r'deviceName\s*=\s*(.+)', line)
                        if match:
                            gpu_name = match.group(1).strip()
                            gpus.append({'id': gpu_id, 'name': gpu_name})
                            gpu_id += 1
        
        elif system == "Linux":
            result = subprocess.run(
                ["vulkaninfo", "--summary"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                gpu_id = 0
                for line in lines:
                    if 'deviceName' in line:
                        match = re.search(r'deviceName\s*=\s*(.+)', line)
                        if match:
                            gpu_name = match.group(1).strip()
                            gpus.append({'id': gpu_id, 'name': gpu_name})
                            gpu_id += 1
        
        elif system == "Darwin":
            result = subprocess.run(
                ["vulkaninfo", "--summary"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                gpu_id = 0
                for line in lines:
                    if 'deviceName' in line:
                        match = re.search(r'deviceName\s*=\s*(.+)', line)
                        if match:
                            gpu_name = match.group(1).strip()
                            gpus.append({'id': gpu_id, 'name': gpu_name})
                            gpu_id += 1
    
    except FileNotFoundError:
        pass
    except subprocess.TimeoutExpired:
        pass
    except Exception:
        pass
    
    return gpus

def list_gpus():
    print("\n" + "="*67)
    print("DETECTED VULKAN GPUS")
    print("="*67 + "\n")
    
    gpus = detect_vulkan_gpus()
    
    if not gpus:
        print("No Vulkan GPUs detected or vulkaninfo not available.\n")
        print("Make sure you have:")
        print("  - Vulkan drivers installed")
        print("  - vulkaninfo utility available in your PATH\n")
        
        system = platform.system()
        if system == "Windows":
            print("Install Vulkan SDK from: https://vulkan.lunarg.com/\n")
        elif system == "Linux":
            print("Install vulkan-tools: sudo apt install vulkan-tools\n")
        elif system == "Darwin":
            print("Install Vulkan SDK from: https://vulkan.lunarg.com/\n")
        return
    
    print(f"Found {len(gpus)} Vulkan device(s):\n")
    
    for gpu in gpus:
        print(f"  GPU {gpu['id']}: {gpu['name']}")
    
    print(f"\nTo use a specific GPU, add: --gpu {gpus[0]['id']}")
    print(f"Example: python manga_upscaler.py -i ./input --gpu 1\n")

def check_waifu2x_installed():
    system = platform.system()
    exe_name = "waifu2x-ncnn-vulkan.exe" if system == "Windows" else "waifu2x-ncnn-vulkan"
    waifu_bin = BIN_DIR / exe_name
    models_dir = MODELS_DIR / "waifu2x" / "models-cunet"
    
    if not waifu_bin.exists():
        return False, f"Binary not found: {waifu_bin}"
    
    if not models_dir.exists():
        return False, f"Models directory not found: {models_dir}"
    
    if not any(models_dir.iterdir()):
        return False, f"Models directory is empty: {models_dir}"
    
    return True, "OK"

def verify_model_requirements(model_name):
    model_config = AVAILABLE_MODELS.get(model_name)
    if not model_config:
        raise ModelError(f"Unknown model: {model_name}")
    
    errors = []
    
    if model_name == "waifu2x":
        installed, msg = check_waifu2x_installed()
        if not installed:
            errors.append(f"[X] Waifu2x: {msg}")
            errors.append(f"    Run: python manga_upscaler.py --download waifu2x")
    
    if errors:
        error_text = "\n".join(errors)
        raise ModelError(f"\nModel requirements not met:\n\n{error_text}\n")

def download_waifu2x():
    import time
    
    BIN_DIR.mkdir(exist_ok=True)
    
    system = platform.system()
    if system == "Windows":
        url = "https://github.com/nihui/waifu2x-ncnn-vulkan/releases/download/20220728/waifu2x-ncnn-vulkan-20220728-windows.zip"
        exe_name = "waifu2x-ncnn-vulkan.exe"
    elif system == "Linux":
        url = "https://github.com/nihui/waifu2x-ncnn-vulkan/releases/download/20220728/waifu2x-ncnn-vulkan-20220728-ubuntu.zip"
        exe_name = "waifu2x-ncnn-vulkan"
    elif system == "Darwin":
        url = "https://github.com/nihui/waifu2x-ncnn-vulkan/releases/download/20220728/waifu2x-ncnn-vulkan-20220728-macos.zip"
        exe_name = "waifu2x-ncnn-vulkan"
    else:
        raise ModelError(f"Unsupported operating system: {system}")
    
    print("="*67)
    print("DOWNLOADING WAIFU2X MODEL")
    print("="*67 + "\n")
    print(f"Downloading waifu2x-ncnn-vulkan...")
    print(f"   Source: GitHub/nihui/waifu2x-ncnn-vulkan")
    print(f"   Platform: {system}\n")
    
    zip_path = BIN_DIR / "waifu2x.zip"
    
    if zip_path.exists():
        zip_path.unlink()
    
    try:
        urllib.request.urlretrieve(url, zip_path, DownloadProgressBar())
        print(f"   Download complete!\n")
    except Exception as e:
        if zip_path.exists():
            zip_path.unlink()
        raise ModelError(f"Download failed: {e}")
    
    print("Extracting archive...")
    temp_dir = BIN_DIR / "temp_extract"
    
    try:
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
            time.sleep(0.3)
        
        temp_dir.mkdir(exist_ok=True)
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        time.sleep(0.5)
        
        exe_found = None
        for item in temp_dir.rglob("*"):
            if item.is_file() and item.name in [exe_name, "waifu2x-ncnn-vulkan", "waifu2x-ncnn-vulkan.exe"]:
                exe_found = item
                break
        
        if not exe_found:
            raise ModelError("Could not find executable in archive")
        
        final_exe = BIN_DIR / exe_name
        if final_exe.exists():
            final_exe.unlink()
            time.sleep(0.2)
        
        shutil.copy2(exe_found, final_exe)
        print(f"   Installed: {exe_name}")
        
        if system != "Windows":
            os.chmod(final_exe, 0o755)
        
        models_copied = []
        for item in temp_dir.rglob("*"):
            if item.is_dir() and item.name.startswith("models-"):
                model_name = item.name
                final_model_dir = MODELS_DIR / "waifu2x" / model_name
                
                if final_model_dir.exists():
                    shutil.rmtree(final_model_dir, ignore_errors=True)
                    time.sleep(0.2)
                
                final_model_dir.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(item, final_model_dir)
                models_copied.append(model_name)
        
        if models_copied:
            print(f"   Installed models: {', '.join(models_copied)}")
        else:
            raise ModelError("No model directories found in archive")
        
        time.sleep(0.5)
        shutil.rmtree(temp_dir, ignore_errors=True)
        if zip_path.exists():
            zip_path.unlink()
        
        print(f"\n" + "="*67)
        print(f"WAIFU2X INSTALLED SUCCESSFULLY")
        print("="*67 + "\n")
            
    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        if zip_path.exists():
            zip_path.unlink()
        raise ModelError(f"Extraction failed: {e}")

def zip_directory(dir_path, zip_path, description="", cleanup=False):
    import time
    
    try:
        all_files = list(dir_path.rglob("*"))
        files_to_zip = [f for f in all_files if f.is_file()]
        
        if not files_to_zip:
            print(f"   No files to zip in {dir_path.name}")
            return False
        
        print(f"   Zipping: {dir_path.name} ({len(files_to_zip)} files)")
        progress = ProgressTracker(len(files_to_zip), "Zipping")
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_STORED) as zipf:
            for file_path in files_to_zip:
                arcname = file_path.relative_to(dir_path.parent)
                zipf.write(file_path, arcname)
                progress.update(file_path.name)
        
        progress.finish()
        
        zip_size_mb = zip_path.stat().st_size / (1024 * 1024)
        print(f"   Created: {zip_path.name} ({zip_size_mb:.1f} MB)")
        
        if cleanup:
            try:
                time.sleep(0.2)
                shutil.rmtree(dir_path)
                print(f"   Removed: {dir_path.name}")
            except Exception as e:
                print(f"   Warning: Could not remove {dir_path.name}: {e}")
        
        print()
        return True
        
    except Exception as e:
        print(f"   Failed to zip {dir_path.name}: {e}\n")
        return False

def run_waifu2x(input_path, output_path, quality_settings=None, progress_tracker=None):
    system = platform.system()
    exe_name = "waifu2x-ncnn-vulkan.exe" if system == "Windows" else "waifu2x-ncnn-vulkan"
    waifu_bin = BIN_DIR / exe_name
    models_dir = MODELS_DIR / "waifu2x" / "models-cunet"

    output_path.mkdir(parents=True, exist_ok=True)
    
    if input_path.is_file():
        images = [input_path]
    else:
        images = list(input_path.glob("*.png")) + list(input_path.glob("*.jpg")) + \
                 list(input_path.glob("*.jpeg")) + list(input_path.glob("*.webp"))
        images = sorted(images)
    
    if not images:
        print("   No images found")
        return
    
    for idx, img_path in enumerate(images, 1):
        out_file = output_path / img_path.name
        
        cmd = [
            str(waifu_bin),
            "-i", str(img_path),
            "-o", str(out_file),
            "-s", "2",
            "-m", str(models_dir)
        ]
        
        if quality_settings:
            if "denoise_level" in quality_settings:
                cmd.extend(["-n", str(quality_settings["denoise_level"])])
            else:
                cmd.extend(["-n", "0"])
                
            if "tile_size" in quality_settings and quality_settings["tile_size"] > 0:
                cmd.extend(["-t", str(quality_settings["tile_size"])])
                
            if "gpu_id" in quality_settings:
                cmd.extend(["-g", str(quality_settings["gpu_id"])])
        else:
            cmd.extend(["-n", "0"])
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                if progress_tracker:
                    progress_tracker.update(img_path.name)
            else:
                if progress_tracker:
                    progress_tracker.update(f"{img_path.name} (failed)")
                    
        except subprocess.TimeoutExpired:
            if progress_tracker:
                progress_tracker.update(f"{img_path.name} (timeout)")
        except Exception as e:
            if progress_tracker:
                progress_tracker.update(f"{img_path.name} (error)")

def process_images(input_dir, output_dir, model_name, nested=False, quality_settings=None, zip_output=False, zip_nested=False):
    input_path = Path(input_dir)
    output_path = Path(output_dir)

    if not input_path.exists():
        raise FileNotFoundError(f"Input directory not found: {input_path}")

    print("Checking model requirements...\n")
    verify_model_requirements(model_name)
    print("All requirements met!\n")
    
    if quality_settings:
        print("Quality Settings:")
        for key, value in quality_settings.items():
            if key == "gpu_id":
                gpus = detect_vulkan_gpus()
                gpu_name = None
                for gpu in gpus:
                    if gpu['id'] == value:
                        gpu_name = gpu['name']
                        break
                if gpu_name:
                    print(f"   {key}: {value} ({gpu_name})")
                else:
                    print(f"   {key}: {value}")
            else:
                print(f"   {key}: {value}")
        print()

    if model_name == "waifu2x":
        print("Using waifu2x x2 (fast manga mode)\n")
        
        if nested:
            print(f"Scanning nested structure in: {input_path}\n")
            subdirs = [d for d in input_path.iterdir() if d.is_dir()]
            
            if not subdirs:
                print("No subdirectories found. Processing as flat directory...\n")
                images = list(input_path.glob("*.png")) + list(input_path.glob("*.jpg")) + \
                         list(input_path.glob("*.jpeg")) + list(input_path.glob("*.webp"))
                progress = ProgressTracker(len(images), "Upscaling")
                run_waifu2x(input_path, output_path, quality_settings, progress)
                progress.finish()
            else:
                print(f"Found {len(subdirs)} subdirectories (chapters)\n")
                print("=" * 70)
                
                total_images = 0
                for subdir in subdirs:
                    images = list(subdir.glob("*.png")) + list(subdir.glob("*.jpg")) + \
                             list(subdir.glob("*.jpeg")) + list(subdir.glob("*.webp"))
                    total_images += len(images)
                
                print(f"Total: {len(subdirs)} chapters, {total_images} images\n")
                progress = ProgressTracker(total_images, "Overall Progress")
                
                for idx, subdir in enumerate(sorted(subdirs), 1):
                    print(f"\nChapter [{idx}/{len(subdirs)}]: {subdir.name}")
                    print("-" * 70)
                    
                    sub_output = output_path / subdir.name
                    
                    try:
                        run_waifu2x(subdir, sub_output, quality_settings, progress)
                        print(f"   Completed: {subdir.name}\n")
                    except subprocess.CalledProcessError as e:
                        print(f"   Failed to process {subdir.name}: {e}\n")
                
                progress.finish()
                print("\n" + "=" * 70)
                print("All chapters processed successfully")
                print("=" * 70)
                
                if zip_nested:
                    print("\n" + "="*67)
                    print("ZIPPING CHAPTERS")
                    print("="*67 + "\n")
                    
                    zipped_count = 0
                    for subdir in sorted(output_path.iterdir()):
                        if subdir.is_dir():
                            zip_path = output_path / f"{subdir.name}.zip"
                            if zip_directory(subdir, zip_path, cleanup=True):
                                zipped_count += 1
                    
                    if zipped_count > 0:
                        print("=" * 70)
                        print(f"Successfully zipped {zipped_count} chapter(s)")
                        print(f"Removed {zipped_count} original folder(s) to save space")
                        print("=" * 70)
        else:
            images = list(input_path.glob("*.png")) + list(input_path.glob("*.jpg")) + \
                     list(input_path.glob("*.jpeg")) + list(input_path.glob("*.webp"))
            print(f"Found {len(images)} images to process\n")
            progress = ProgressTracker(len(images), "Upscaling")
            run_waifu2x(input_path, output_path, quality_settings, progress)
            progress.finish()
            
            if zip_output:
                print("\n" + "="*67)
                print("ZIPPING OUTPUT")
                print("="*67 + "\n")
                
                zip_path = output_path.parent / f"{output_path.name}.zip"
                if zip_directory(output_path, zip_path, cleanup=True):
                    print("=" * 70)
                    print(f"Output zipped successfully")
                    print(f"Removed original folder to save space")
                    print("=" * 70)
        return

def list_models():
    print("\n" + "="*67)
    print("AVAILABLE MODELS")
    print("="*67 + "\n")
    
    for model_name, config in AVAILABLE_MODELS.items():
        print(f"{model_name}")
        print(f"   Description: {config['description']}")
        print(f"   Scale: {config['scale']}x")
        print(f"   Type: {config['type']}")
        
        installed, msg = check_waifu2x_installed()
        if installed:
            print(f"   Status: Installed")
        else:
            print(f"   Status: Not installed")
            print(f"   Install: python manga_upscaler.py --download waifu2x")
        
        print()

def show_usage():
    print("\n" + "="*67)
    print("MANGA AI UPSCALER - USAGE")
    print("="*67 + "\n")
    
    print("BASIC USAGE:")
    print("  python manga_upscaler.py -i INPUT_DIR [-o OUTPUT_DIR] [-m MODEL] [-q PRESET]\n")
    
    print("EXAMPLES:")
    print("  # Upscale with waifu2x (default, fast)")
    print("  python manga_upscaler.py -i ./manga_folder\n")
    
    print("  # Use quality preset (fast, balanced, quality)")
    print("  python manga_upscaler.py -i ./manga_folder -q quality\n")
    
    print("  # Custom denoise level for waifu2x")
    print("  python manga_upscaler.py -i ./manga_folder --denoise 2\n")
    
    print("  # Use specific GPU")
    print("  python manga_upscaler.py -i ./manga_folder --gpu 1\n")
    
    print("  # Process nested folder structure (chapters)")
    print("  python manga_upscaler.py -i ./manga_series --nested\n")
    
    print("  # Specify output directory")
    print("  python manga_upscaler.py -i ./input -o ./output\n")
    
    print("  # Create upscaled subfolder in input directory")
    print("  python manga_upscaler.py -i ./manga_folder --subdir\n")
    
    print("  # Zip output after processing")
    print("  python manga_upscaler.py -i ./manga_folder --zip\n")
    
    print("  # Process nested structure and zip each chapter")
    print("  python manga_upscaler.py -i ./manga_series --nested --zip-chapters\n")
    
    print("QUALITY PRESETS:")
    print("  -q fast         Fast processing with lower quality")
    print("  -q balanced     Balanced quality and speed (default)")
    print("  -q quality      Best quality, slower processing\n")
    
    print("QUALITY SETTINGS (Manual Override):")
    print("  --denoise N     [waifu2x] Denoise level: -1=none, 0=low, 1-3=higher")
    print("  --tile-size N   Tile size: 0=auto, 32-2048 for manual control")
    print("  --gpu N         GPU device ID to use (default: 0)\n")
    
    print("GPU MANAGEMENT:")
    print("  # List detected GPUs and their IDs")
    print("  python manga_upscaler.py --list-gpus\n")
    
    print("MODEL MANAGEMENT:")
    print("  # List available models and their status")
    print("  python manga_upscaler.py --list-models\n")
    
    print("  # Download waifu2x model")
    print("  python manga_upscaler.py --download waifu2x\n")
    
    print("OPTIONS:")
    print("  -i, --input DIR       Input directory containing images")
    print("  -o, --output DIR      Output directory (default: INPUT_upscaled)")
    print("  --subdir              Create 'upscaled' folder in input directory")
    print("  --nested              Process nested folder structure (chapters)")
    print("  -m, --model NAME      Model to use (default: waifu2x)")
    print("  -q, --quality PRESET  Quality preset: fast, balanced, quality")
    print("  --gpu N               GPU device ID to use (default: 0)")
    print("  --zip                 Zip output directory after processing and remove original folder")
    print("  --zip-chapters        Zip each chapter separately (with --nested) and remove original folders")
    print("  --list-gpus           List all detected Vulkan GPUs")
    print("  --list-models         List all available models and their status")
    print("  --download MODEL      Download a specific model")
    print("  -h, --help            Show this help message\n")
    
    print("ZIPPING OPTIONS:")
    print("  --zip                 Zip entire output directory (storage only, no compression)")
    print("                        Automatically removes original folder after zipping")
    print("  --zip-chapters        With --nested: zip each chapter folder separately")
    print("                        Creates individual .zip files and removes original folders\n")
    
    print("PROGRESS TRACKING:")
    print("  The tool shows real-time progress bars for all operations:")
    print("  - Download progress with percentage and speed")
    print("  - Image processing progress: [█████░░░] 50% [5/10] filename.png")
    print("  - Overall progress for nested folder structures\n")

def main():
    parser = argparse.ArgumentParser(add_help=False)
    
    parser.add_argument("-i", "--input", type=str, help="Input directory path")
    parser.add_argument("-o", "--output", type=str, help="Output directory path")
    parser.add_argument("--subdir", action="store_true", 
                       help="Create 'upscaled' subdirectory in input folder")
    parser.add_argument("--nested", action="store_true", 
                       help="Process nested folders (chapter structure)")
    parser.add_argument("-m", "--model", type=str, default="waifu2x",
                       choices=AVAILABLE_MODELS.keys(),
                       help="Model to use (default: waifu2x)")
    
    parser.add_argument("-q", "--quality", type=str, 
                       choices=["fast", "balanced", "quality"],
                       help="Quality preset: fast, balanced, or quality")
    parser.add_argument("--denoise", type=int, choices=[-1, 0, 1, 2, 3],
                       help="[waifu2x] Denoise level (-1=none, 0=low, 1-3=higher)")
    parser.add_argument("--tile-size", type=int,
                       help="Tile size for processing (0=auto, 32-2048 manual)")
    parser.add_argument("--gpu", type=int, default=0,
                       help="GPU device ID to use (default: 0)")
    
    parser.add_argument("--zip", action="store_true",
                       help="Zip output directory after processing and remove original folder")
    parser.add_argument("--zip-chapters", action="store_true",
                       help="Zip each chapter separately (with --nested) and remove original folders")
    
    parser.add_argument("--list-gpus", action="store_true",
                       help="List all detected Vulkan GPUs and their IDs")
    
    parser.add_argument("--list-models", action="store_true",
                       help="List all available models and their status")
    parser.add_argument("--download", type=str, choices=AVAILABLE_MODELS.keys(),
                       help="Download a specific model")
    
    parser.add_argument("-h", "--help", action="store_true",
                       help="Show help message")
    
    if len(sys.argv) == 1:
        show_usage()
        sys.exit(0)
    
    args = parser.parse_args()
    
    if args.help:
        show_usage()
        sys.exit(0)
    
    if args.list_gpus:
        list_gpus()
        sys.exit(0)
    
    if args.list_models:
        list_models()
        sys.exit(0)
    
    if args.download:
        try:
            if args.download == "waifu2x":
                download_waifu2x()
            sys.exit(0)
        except ModelError as e:
            print(f"\nError: {e}\n")
            sys.exit(1)
    
        try:
            sys.exit(0)
        except Exception as e:
            print(f"\nError setting up environment: {e}\n")
            sys.exit(1)
    
    if not args.input:
        print("Error: Input directory is required for processing!")
        print("\nRun 'python manga_upscaler.py --help' for usage information.")
        sys.exit(1)
    
    input_path = Path(args.input)
    if args.output:
        output_path = Path(args.output)
    elif args.subdir:
        output_path = input_path / "upscaled"
    else:
        output_path = input_path.parent / f"{input_path.name}_upscaled"
    
    quality_settings = {}
    
    if args.quality:
        if args.model in QUALITY_PRESETS:
            quality_settings = QUALITY_PRESETS[args.model][args.quality].copy()
    else:
        if args.model in QUALITY_PRESETS:
            quality_settings = QUALITY_PRESETS[args.model]["balanced"].copy()
    
    if args.denoise is not None:
        quality_settings["denoise_level"] = args.denoise
    if args.tile_size is not None:
        quality_settings["tile_size"] = args.tile_size
    if args.gpu is not None:
        quality_settings["gpu_id"] = args.gpu
    
    print("\n" + "="*67)
    print("MANGA AI UPSCALER - Configuration")
    print("="*67)
    print(f"  Input:          {input_path}")
    print(f"  Output:         {output_path}")
    print(f"  Model:          {args.model}")
    print(f"  Scale:          2x")
    print(f"  Nested:         {'Yes' if args.nested else 'No'}")
    if args.quality:
        print(f"  Quality Preset: {args.quality}")
    if args.zip:
        print(f"  Zip Output:     Yes")
    if args.zip_chapters and args.nested:
        print(f"  Zip Chapters:   Yes")
    print("="*67 + "\n")
    
    try:
        process_images(
            input_dir=input_path,
            output_dir=output_path,
            model_name=args.model,
            nested=args.nested,
            quality_settings=quality_settings if quality_settings else None,
            zip_output=args.zip,
            zip_nested=args.zip_chapters
        )
    except ModelError as e:
        print(f"\n{e}")
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"\nError: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()