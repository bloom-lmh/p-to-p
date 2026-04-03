"""
PNG to SVG Converter - Web Application
"""

from flask import Flask, render_template, request, jsonify, send_file, abort
from functools import lru_cache
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from threading import Lock
from xml.etree import ElementTree as ET

from PIL import Image, ImageFilter
import numpy as np
from skimage.metrics import structural_similarity as ssim
from skimage.metrics import peak_signal_noise_ratio as psnr
from vtracer import convert_image_to_svg_py
from svgelements import Path as SvgPath, Matrix

try:
    import cairosvg
except (ImportError, OSError):
    cairosvg = None

try:
    from svglib.svglib import svg2rlg
    from reportlab.graphics import renderPM
except ImportError:
    svg2rlg = None
    renderPM = None


# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ET.register_namespace('', 'http://www.w3.org/2000/svg')
SVG_NUMBER_RE = re.compile(r'-?\d+(?:\.\d+)?')
INKSCAPE_CANDIDATES = (
    r'C:\Program Files\Inkscape\bin\inkscape.exe',
    r'C:\Program Files\Inkscape\inkscape.exe',
    r'C:\Program Files (x86)\Inkscape\bin\inkscape.exe',
    r'C:\Program Files (x86)\Inkscape\inkscape.exe',
)


app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'outputs'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

jobs = {}
jobs_lock = Lock()


def get_presets() -> dict:
    """Preset definitions shared by conversion and the preset API."""
    return {
        'clean': {
            'name': 'Clean',
            'description': 'Minimal detail for logos, icons, and flat graphics',
            'cp': 3,
            'fs': 15,
            'ct': 60,
            'lt': 12,
            'ld': 20,
            'scale': 2,
            'mode': 'spline',
            'hierarchical': 'stacked',
            'path_precision': 4,
        },
        'balanced': {
            'name': 'Balanced',
            'description': 'Recommended balance of quality and file size',
            'cp': 5,
            'fs': 6,
            'ct': 45,
            'lt': 5,
            'ld': 10,
            'scale': 2,
            'mode': 'spline',
            'hierarchical': 'stacked',
            'path_precision': 4,
        },
        'detailed': {
            'name': 'Detailed',
            'description': 'Keep more detail for complex artwork',
            'cp': 6,
            'fs': 2,
            'ct': 30,
            'lt': 3,
            'ld': 4,
            'scale': 3,
            'mode': 'spline',
            'hierarchical': 'stacked',
            'path_precision': 4,
        },
        'ultra': {
            'name': 'Ultra',
            'description': 'Highest fidelity and the largest file size',
            'cp': 8,
            'fs': 1,
            'ct': 20,
            'lt': 2,
            'ld': 2,
            'scale': 3,
            'mode': 'spline',
            'hierarchical': 'stacked',
            'path_precision': 4,
        },
        'ppt': {
            'name': 'Balanced + PPT',
            'description': 'Legacy shortcut: Balanced tracing plus PowerPoint cleanup',
            'cp': 5,
            'fs': 6,
            'ct': 45,
            'lt': 5,
            'ld': 10,
            'scale': 2,
            'mode': 'spline',
            'hierarchical': 'stacked',
            'path_precision': 4,
            'powerpoint_optimize': True,
        },
    }


def svg_to_png(svg_path: str, output_path: str, width: int = None):
    """Convert SVG to PNG for comparison."""
    try:
        if cairosvg is not None:
            cairosvg.svg2png(url=svg_path, write_to=output_path, output_width=width)
            return

        if svg2rlg is None or renderPM is None:
            raise RuntimeError("No SVG rasterizer is available")

        drawing = svg2rlg(svg_path)
        if drawing is None:
            raise RuntimeError("Failed to parse SVG drawing")

        if width and drawing.width:
            scale = width / float(drawing.width)
            drawing.width *= scale
            drawing.height *= scale
            drawing.scale(scale, scale)

        renderPM.drawToFile(drawing, output_path, fmt='PNG', backend='rlPyCairo')
    except Exception:
        Image.new('RGB', (100, 100), color='white').save(output_path)


def evaluate_quality(original_path: str, svg_path: str) -> dict:
    """Evaluate the quality of vectorized image."""
    if cairosvg is None and (svg2rlg is None or renderPM is None):
        return None

    original_img = Image.open(original_path)
    if original_img.mode != 'RGB':
        original_img = original_img.convert('RGB')

    temp_png = tempfile.mktemp(suffix='.png')
    svg_to_png(svg_path, temp_png, width=original_img.width)

    vector_img = Image.open(temp_png)
    if vector_img.mode != 'RGB':
        vector_img = vector_img.convert('RGB')
    if vector_img.size != original_img.size:
        vector_img = vector_img.resize(original_img.size)

    original_np = np.array(original_img)
    vector_np = np.array(vector_img)

    results = {}
    try:
        results['ssim'] = float(
            ssim(original_np, vector_np, multichannel=True, channel_axis=2, data_range=255)
        )
    except Exception:
        results['ssim'] = 0.0

    try:
        results['psnr'] = float(psnr(original_np, vector_np, data_range=255))
    except Exception:
        results['psnr'] = 0.0

    try:
        results['mse'] = float(np.mean((original_np.astype(float) - vector_np.astype(float)) ** 2))
    except Exception:
        results['mse'] = float('inf')

    ssim_val = results.get('ssim', 0)
    psnr_val = results.get('psnr', 0)
    if ssim_val >= 0.94:
        score = ssim_val * 100
    else:
        score = ssim_val * 60 + min(psnr_val * 2.5, 25)

    results['score'] = max(0, min(100, score))

    try:
        os.remove(temp_png)
    except Exception:
        pass

    return results


def count_svg_paths(svg_path: str) -> int:
    """Count path nodes in an SVG without loading the whole file into memory."""
    count = 0
    with open(svg_path, 'r', encoding='utf-8', errors='ignore') as svg_file:
        while True:
            chunk = svg_file.read(1024 * 1024)
            if not chunk:
                break
            count += chunk.count('<path ')
    return count


def compact_svg_numbers(text: str, decimals: int = 3) -> str:
    """Reduce noisy float precision after transform flattening."""
    def replace_number(match):
        value = float(match.group(0))
        rounded = f'{value:.{decimals}f}'.rstrip('0').rstrip('.')
        if rounded == '-0':
            return '0'
        return rounded

    return SVG_NUMBER_RE.sub(replace_number, text)


@lru_cache(maxsize=1)
def get_inkscape_path() -> str | None:
    """Locate an Inkscape binary for optional Office-friendly exports."""
    path = shutil.which('inkscape')
    if path and os.path.exists(path):
        return path

    for candidate in INKSCAPE_CANDIDATES:
        if os.path.exists(candidate):
            return candidate

    return None


def can_export_emf() -> bool:
    """Whether the environment can produce EMF files for PowerPoint."""
    return get_inkscape_path() is not None


def optimize_svg_for_powerpoint(svg_path: str, decimals: int = 3):
    """Flatten transforms and add a viewBox for better PowerPoint compatibility."""
    tree = ET.parse(svg_path)
    root = tree.getroot()

    width = (root.get('width') or '').replace('px', '')
    height = (root.get('height') or '').replace('px', '')
    if width and height and not root.get('viewBox'):
        root.set('viewBox', f'0 0 {width} {height}')

    for elem in root.iter():
        if not elem.tag.endswith('path') or not elem.get('d'):
            continue

        path = SvgPath(elem.get('d'))
        transform = elem.get('transform')
        if transform:
            path *= Matrix(transform)
            elem.attrib.pop('transform', None)

        elem.set('d', compact_svg_numbers(path.d(relative=True), decimals))

    tree.write(svg_path, encoding='utf-8', xml_declaration=True)


def export_svg_to_emf(svg_path: str, emf_path: str):
    """Export a cleaned SVG to EMF via Inkscape for Office compatibility."""
    inkscape_path = get_inkscape_path()
    if not inkscape_path:
        raise RuntimeError('Inkscape is not available for EMF export')

    command = [
        inkscape_path,
        svg_path,
        f'--export-filename={emf_path}',
        '--export-type=emf',
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if completed.returncode != 0 or not os.path.exists(emf_path):
        message = completed.stderr.strip() or completed.stdout.strip() or 'Unknown Inkscape error'
        raise RuntimeError(f'EMF export failed: {message}')


def preprocess_image_for_tracing(input_path: str, params: dict) -> str:
    """Prepare the raster input for tracing."""
    with Image.open(input_path) as img:
        has_alpha = 'A' in img.getbands() or 'transparency' in img.info
        img = img.convert('RGBA' if has_alpha else 'RGB')

        max_dimension = params.get('max_dimension')
        if max_dimension and max(img.size) > max_dimension:
            resize_scale = max_dimension / max(img.size)
            new_size = (
                max(1, int(img.width * resize_scale)),
                max(1, int(img.height * resize_scale)),
            )
            img = img.resize(new_size, Image.Resampling.LANCZOS)

        scale = params.get('scale', 1)
        if not max_dimension and img.width > 3000 and scale > 1:
            scale = max(1, scale // 2)
        if scale > 1:
            img = img.resize(
                (int(img.width * scale), int(img.height * scale)),
                Image.Resampling.LANCZOS,
            )

        median_filter_size = params.get('median_filter')
        if median_filter_size and median_filter_size >= 3:
            img = img.filter(ImageFilter.MedianFilter(size=median_filter_size))

        quantize_colors = params.get('quantize_colors')
        if quantize_colors:
            if has_alpha:
                alpha = img.getchannel('A')
                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                rgb_img.paste(img.convert('RGB'), mask=alpha)
                rgb_img = rgb_img.quantize(
                    colors=quantize_colors,
                    method=Image.Quantize.MEDIANCUT,
                ).convert('RGB')

                quantized = Image.new('RGBA', img.size, (255, 255, 255, 0))
                quantized.paste(rgb_img, mask=alpha)
                quantized.putalpha(alpha)
                img = quantized
            else:
                img = img.convert('RGB').quantize(
                    colors=quantize_colors,
                    method=Image.Quantize.MEDIANCUT,
                ).convert('RGB')

        temp_png = tempfile.mktemp(suffix='.png')
        img.save(temp_png, 'PNG')

    return temp_png


def convert_image(
    input_path: str,
    output_path: str,
    preset: str = 'balanced',
    powerpoint_optimize: bool = False,
) -> dict:
    """Convert image to SVG with the specified preset."""
    presets = get_presets()
    params = presets.get(preset, presets['balanced'])
    should_optimize_for_powerpoint = bool(powerpoint_optimize or params.get('powerpoint_optimize'))

    temp_png = preprocess_image_for_tracing(input_path, params)

    convert_image_to_svg_py(
        temp_png,
        output_path,
        colormode='color',
        hierarchical=params.get('hierarchical', 'stacked'),
        mode=params.get('mode', 'spline'),
        filter_speckle=params['fs'],
        color_precision=params['cp'],
        layer_difference=params['ld'],
        corner_threshold=params['ct'],
        length_threshold=params['lt'],
        max_iterations=10,
        splice_threshold=45,
        path_precision=params.get('path_precision', 4),
    )

    if should_optimize_for_powerpoint:
        optimize_svg_for_powerpoint(output_path)

    try:
        os.remove(temp_png)
    except Exception:
        pass

    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)

    return {
        'preset': preset,
        'preset_name': params['name'],
        'file_size_mb': round(file_size_mb, 2),
        'path_count': count_svg_paths(output_path),
        'editable': should_optimize_for_powerpoint,
        'powerpoint_optimized': should_optimize_for_powerpoint,
    }


@app.route('/')
def index():
    """Main page."""
    return render_template(
        'index.html',
        office_export_available=can_export_emf(),
    )


@app.route('/api/convert', methods=['POST'])
def api_convert():
    """Convert image to SVG."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    allowed_extensions = {'.png', '.jpg', '.jpeg', '.PNG', '.JPG', '.JPEG'}
    if not any(file.filename.endswith(ext) for ext in allowed_extensions):
        return jsonify({'error': 'Invalid file type. Use PNG, JPG, or JPEG.'}), 400

    preset = request.form.get('preset', 'balanced')
    evaluate = request.form.get('evaluate', 'true').lower() == 'true'
    powerpoint_optimize = request.form.get('powerpoint_optimize', 'false').lower() == 'true'

    job_id = str(uuid.uuid4())
    input_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{job_id}_{file.filename}")
    file.save(input_path)

    output_filename = f"{job_id}.svg"
    output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)

    try:
        with jobs_lock:
            jobs[job_id] = {'status': 'processing', 'progress': 0}

        result = convert_image(
            input_path,
            output_path,
            preset=preset,
            powerpoint_optimize=powerpoint_optimize,
        )
        metrics = evaluate_quality(input_path, output_path) if evaluate else None
        downloads = {
            'svg': output_filename,
        }

        if powerpoint_optimize and can_export_emf():
            emf_filename = f"{job_id}.emf"
            emf_path = os.path.join(app.config['OUTPUT_FOLDER'], emf_filename)
            try:
                export_svg_to_emf(output_path, emf_path)
                downloads['emf'] = emf_filename
            except Exception as exc:
                result['office_export_error'] = str(exc)

        result['downloads'] = downloads
        result['recommended_download'] = 'emf' if 'emf' in downloads else 'svg'

        with jobs_lock:
            jobs[job_id] = {
                'status': 'completed',
                'progress': 100,
                'output_file': output_filename,
                'metrics': metrics,
                'result': result,
            }

        return jsonify({
            'job_id': job_id,
            'status': 'completed',
            'output_file': output_filename,
            'metrics': metrics,
            'result': result,
        })
    except Exception as exc:
        with jobs_lock:
            jobs[job_id] = {
                'status': 'error',
                'error': str(exc),
            }
        return jsonify({'error': str(exc)}), 500


@app.route('/api/status/<job_id>')
def api_status(job_id):
    """Get job status."""
    with jobs_lock:
        job = jobs.get(job_id)

    if job is None:
        return jsonify({'error': 'Job not found'}), 404

    return jsonify(job)


@app.route('/download/<filename>')
def download(filename):
    """Download converted SVG file."""
    file_path = os.path.join(app.config['OUTPUT_FOLDER'], filename)
    if not os.path.isfile(file_path):
        abort(404)

    mimetype = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'
    return send_file(file_path, as_attachment=True, mimetype=mimetype)


@app.route('/api/presets')
def api_presets():
    """Get available presets."""
    return jsonify({
        'capabilities': {
            'emf_export': can_export_emf(),
            'preferred_powerpoint_download': 'emf' if can_export_emf() else 'svg',
        },
        'presets': [
            {
                'id': preset_id,
                'name': preset['name'],
                'description': preset['description'],
            }
            for preset_id, preset in get_presets().items()
        ]
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
