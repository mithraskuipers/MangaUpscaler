# Manga AI Upscaler

A Python-based tool for upscaling manga and comic images using AI models. Built with support for GPU acceleration via Vulkan and optimized for batch processing of large manga collections.

## Features

- **AI-Powered Upscaling**: Uses waifu2x-ncnn-vulkan for high-quality 2x upscaling
- **GPU Acceleration**: Full Vulkan GPU support with device selection
- **Batch Processing**: Process entire directories or nested folder structures
- **Quality Presets**: Fast, balanced, and quality modes for different use cases
- **Progress Tracking**: Real-time progress bars for all operations
- **Archive Support**: Automatic ZIP compression with optional cleanup
- **Cross-Platform**: Works on Windows, Linux, and macOS

## Requirements

- Python 3.7 or higher
- Vulkan-compatible GPU and drivers
- vulkaninfo utility (for GPU detection)

### Installing Vulkan

**Windows:**
Download and install the Vulkan SDK from https://vulkan.lunarg.com/

**Linux:**
```bash
sudo apt install vulkan-tools
```

**macOS:**
Download and install the Vulkan SDK from https://vulkan.lunarg.com/

## Installation

1. Clone or download this repository
2. Download the waifu2x model:
```bash
python manga_upscaler.py --download waifu2x
```

## Basic Usage

### Simple Upscaling
```bash
python manga_upscaler.py -i ./manga_folder
```

### Specify Output Directory
```bash
python manga_upscaler.py -i ./input -o ./output
```

### Create Subfolder in Input Directory
```bash
python manga_upscaler.py -i ./manga_folder --subdir
```

## Advanced Usage

### Quality Presets

Use predefined quality settings:

```bash
# Fast processing (lower quality, faster)
python manga_upscaler.py -i ./manga_folder -q fast

# Balanced (default)
python manga_upscaler.py -i ./manga_folder -q balanced

# Best quality (slower)
python manga_upscaler.py -i ./manga_folder -q quality
```

### Custom Quality Settings

Fine-tune processing parameters:

```bash
# Custom denoise level (0-3)
python manga_upscaler.py -i ./manga_folder --denoise 2

# Custom tile size for memory management
python manga_upscaler.py -i ./manga_folder --tile-size 256
```

### GPU Selection

List available GPUs:
```bash
python manga_upscaler.py --list-gpus
```

Select a specific GPU:
```bash
python manga_upscaler.py -i ./manga_folder --gpu 1
```

### Nested Folder Processing

Process manga collections organized by chapters:

```bash
python manga_upscaler.py -i ./manga_series --nested
```

Expected folder structure:
```
manga_series/
├── Chapter 01/
│   ├── page_001.png
│   ├── page_002.png
│   └── ...
├── Chapter 02/
│   ├── page_001.png
│   └── ...
└── ...
```

### Archive Management

Zip output and remove original files:

```bash
# Zip entire output folder
python manga_upscaler.py -i ./manga_folder --zip

# Zip each chapter separately (with --nested)
python manga_upscaler.py -i ./manga_series --nested --zip-chapters
```

The `--zip` and `--zip-chapters` flags automatically remove the original folders after successful compression to save disk space.

## Command Reference

### Processing Options

| Option | Description |
|--------|-------------|
| `-i, --input DIR` | Input directory containing images (required) |
| `-o, --output DIR` | Output directory (default: INPUT_upscaled) |
| `--subdir` | Create 'upscaled' folder in input directory |
| `--nested` | Process nested folder structure (chapters) |
| `-m, --model NAME` | Model to use (default: waifu2x) |

### Quality Options

| Option | Description |
|--------|-------------|
| `-q, --quality PRESET` | Quality preset: fast, balanced, quality |
| `--denoise N` | Denoise level: -1=none, 0=low, 1-3=higher |
| `--tile-size N` | Tile size: 0=auto, 32-2048 for manual control |
| `--gpu N` | GPU device ID to use (default: 0) |

### Archive Options

| Option | Description |
|--------|-------------|
| `--zip` | Zip output directory and remove original folder |
| `--zip-chapters` | Zip each chapter separately (with --nested) |

### Management Options

| Option | Description |
|--------|-------------|
| `--list-gpus` | List all detected Vulkan GPUs |
| `--list-models` | List available models and status |
| `--download MODEL` | Download a specific model |
| `-h, --help` | Show help message |

## Examples

### Basic Workflow
```bash
# Download model (first time only)
python manga_upscaler.py --download waifu2x

# Check available GPUs
python manga_upscaler.py --list-gpus

# Upscale with quality preset on GPU 1
python manga_upscaler.py -i ./manga -q quality --gpu 1
```

### Batch Processing with Archives
```bash
# Process entire series and create individual chapter archives
python manga_upscaler.py -i ./manga_series --nested --zip-chapters --gpu 0
```

### Custom Quality Processing
```bash
# Maximum quality with custom settings
python manga_upscaler.py -i ./manga -q quality --denoise 3 --tile-size 200 --gpu 1
```

## Performance Tips

1. **GPU Selection**: Use `--list-gpus` to identify your best GPU and select it with `--gpu`
2. **Tile Size**: Reduce tile size if you encounter out-of-memory errors
3. **Quality Presets**: Use 'fast' for quick previews, 'quality' for final output
4. **Denoise Level**: Higher values (2-3) improve quality but increase processing time
5. **Batch Processing**: Process multiple chapters with `--nested` for efficiency

## Supported Image Formats

- PNG
- JPEG/JPG
- WebP

## Output

The upscaled images are saved in the output directory with the same filenames as the input. When using `--nested`, the folder structure is preserved.

Progress bars show:
- Download progress with size and percentage
- Per-image processing progress
- Overall progress for nested structures
- Compression progress when using zip options

## Troubleshooting

### No GPUs Detected
- Ensure Vulkan drivers are installed
- Install vulkaninfo utility
- Check GPU compatibility with Vulkan

### Out of Memory Errors
- Reduce tile size: `--tile-size 256` or `--tile-size 128`
- Use 'fast' quality preset
- Try a different GPU with `--gpu N`

### Model Not Found
- Run `python manga_upscaler.py --download waifu2x`
- Check that bin/ and models/ directories exist

## License

This tool uses waifu2x-ncnn-vulkan by nihui. Please refer to the original project for licensing information.

## Credits

- waifu2x-ncnn-vulkan: https://github.com/nihui/waifu2x-ncnn-vulkan
- Original waifu2x: https://github.com/nagadomi/waifu2x