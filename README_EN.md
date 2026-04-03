# P-to-P

> Convert `PNG / JPG` images into **PowerPoint-friendly SVG** files.  
> The output is real vector paths, not a bitmap wrapped inside a slide-friendly container.

[中文](README.md) | English

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.0-000000?logo=flask&logoColor=white)
![Output](https://img.shields.io/badge/Output-SVG%20%2F%20EMF-0ea5e9)
![License](https://img.shields.io/badge/License-MIT-facc15)

![P-to-P UI](assets/readme/ui-home-cropped.png)

![PNG to PPT-friendly SVG](assets/readme/conversion-showcase.png)

## ✨ What It Does

`P-to-P` is a lightweight image-to-vector web tool built for presentation workflows. It helps turn `PNG / JPG` assets into `SVG` files that are easier for `PowerPoint` to import and use.

- 🖼️ Converts raster images into real `SVG` vector paths
- 🧩 Supports multiple quality presets: `Clean / Balanced / Detailed / Ultra`
- 🪄 Includes **PowerPoint compatibility cleanup** to make exported SVGs easier for Office to accept
- 📏 Automatically adds `viewBox`, flattens `transform`, and reduces noisy coordinate precision
- 📊 Can evaluate output quality with `SSIM / PSNR / score`
- 💾 Lets you download the converted `SVG` directly
- 🧷 On Windows with `Inkscape` installed, it can also export `EMF`

Best for:

- 📌 Turning PNG assets into scalable visuals for PowerPoint slides
- 🎨 Converting logos, icons, illustrations, and diagram-style graphics
- 🔍 Avoiding blurry edges and visible pixelation when images are scaled up

## 🚀 Quick Start

### Run locally

```bash
git clone https://github.com/bloom-lmh/p-to-p.git
cd p-to-p

pip install -r requirements.txt
python app.py
```

Open: `http://127.0.0.1:5000`

### Run with Docker

```bash
git clone https://github.com/bloom-lmh/p-to-p.git
cd p-to-p

docker-compose up -d
```

Open: `http://127.0.0.1:5000`

### Basic workflow

1. Upload a `PNG / JPG` image
2. Choose a quality preset
3. Enable `PowerPoint compatibility cleanup` if the target is PowerPoint
4. Start the conversion and download the result
5. If `EMF` is available, you can also download it for Office workflows

## 📦 Export Modes

| Mode | Description | Best for |
| --- | --- | --- |
| `SVG` standard export | Generates SVG vector paths directly from the selected preset | Web, design work, and general vector usage |
| `SVG` + PowerPoint cleanup | Keeps the tracing preset unchanged and only cleans the exported SVG structure | Importing into PowerPoint and improving compatibility |
| `EMF` export (optional) | Exports an additional EMF based on the cleaned SVG | Traditional Office workflows on Windows |

Notes:

- 🛠️ `PowerPoint compatibility cleanup` does not retrace the image at lower quality
- ⚖️ If you want more detail, use `Detailed` or `Ultra`
- 📎 If SVG support is unstable in your version of PowerPoint, try `EMF` first

---

If this project helps you, a `Star` is always welcome.
