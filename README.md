# P-to-P

> 把 PNG / JPG 转成真正的 SVG，并额外做一层更适合 PowerPoint 导入的兼容清洗。  
> 不再是“位图塞进 PPT” 的方案，而是面向演示文稿工作流的矢量化输出。

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.0-000000?logo=flask&logoColor=white)
![Output](https://img.shields.io/badge/Output-SVG%20%2F%20EMF-0ea5e9)
![License](https://img.shields.io/badge/License-MIT-facc15)

## 项目预览

### 界面截图

![P-to-P UI](assets/readme/ui-home-cropped.png)

### 转换效果

![PNG to PPT-friendly SVG](assets/readme/conversion-showcase.png)

## 这次改进的重点

- 输出结果是**真正的 SVG 路径**，不是位图封装。
- 新增 **PowerPoint 兼容清洗**：
  - 自动补 `viewBox`
  - 展平路径上的 `transform`
  - 压缩坐标精度，减少 Office 解析时的兼容问题
- 保留你选择的画质预设，不靠“强行降质”来换兼容性。
- 在 Windows 且安装 Inkscape 的环境下，可额外导出 **EMF**，通常更适合 Office 工作流。

## 适合什么场景

- 把 PNG 图片转成 PPT 更容易接受的 SVG
- 把 Logo、图标、插画做成可缩放的矢量素材
- 避免位图放大后发虚、锯齿、边缘不干净
- 为 PowerPoint、Keynote、网页或设计稿准备矢量资源

## 功能特性

- 支持上传 `PNG / JPG / JPEG`
- `Clean / Balanced / Detailed / Ultra` 四种画质预设
- 一键开启 PowerPoint 兼容清洗
- 支持 SVG 质量评估：`SSIM / PSNR / 综合分数`
- 转换完成后可查看文件大小、路径数量等信息
- 条件满足时可额外下载 `EMF`
- 提供简洁的 Flask Web 界面
- 支持 Docker 部署

## 导出模式说明

| 模式 | 输出内容 | 适合场景 |
| --- | --- | --- |
| 普通导出 | 原始追踪得到的 SVG | 通用矢量用途、网页、设计稿 |
| PowerPoint 兼容清洗 | 在不重跑追踪参数的前提下整理 SVG 写法 | 需要插入 PPT、提高导入成功率 |
| EMF 导出（可选） | 基于清洗后的 SVG 再导出 EMF | Windows 下更传统的 Office 工作流 |

## 快速开始

### 本地运行

```bash
git clone https://github.com/bloom-lmh/p-to-p.git
cd p-to-p

pip install -r requirements.txt
python app.py
```

打开浏览器访问 [http://127.0.0.1:5000](http://127.0.0.1:5000)

### Docker

```bash
git clone https://github.com/bloom-lmh/p-to-p.git
cd p-to-p

docker-compose up -d
```

打开浏览器访问 [http://127.0.0.1:5000](http://127.0.0.1:5000)

## 使用方式

1. 上传 PNG/JPG 图片
2. 选择合适的画质预设
3. 如果目标是 PowerPoint，勾选“PowerPoint 兼容清洗”
4. 点击转换并下载 SVG
5. 如果页面同时提供 EMF，也可以直接下载 EMF 用于 Office

## 给 PPT 用户的建议

- 想保留更多细节时，优先提高预设到 `Detailed` 或 `Ultra`，不要只靠降低复杂度换兼容。
- `PowerPoint 兼容清洗` 的作用是整理 SVG 写法，不是把图重新追踪成更低质量版本。
- 如果你的 PowerPoint 版本对 SVG 支持不稳定，优先尝试页面提供的 `EMF` 下载。
- 复杂插画在 PPT 里依然可能比较重，这时建议在画质和可编辑性之间做平衡。

## API

### `POST /api/convert`

上传并转换图片。

请求参数：

- `file`: 图片文件
- `preset`: 画质预设
- `evaluate`: 是否评估质量
- `powerpoint_optimize`: 是否开启 PowerPoint 兼容清洗

示例响应：

```json
{
  "job_id": "uuid",
  "status": "completed",
  "output_file": "output.svg",
  "metrics": {
    "ssim": 0.95,
    "psnr": 25.3,
    "score": 95.0
  },
  "result": {
    "preset": "balanced",
    "preset_name": "Balanced",
    "file_size_mb": 0.26,
    "path_count": 457,
    "powerpoint_optimized": true
  }
}
```

### 其他接口

- `GET /api/presets`：获取预设列表
- `GET /api/status/<job_id>`：获取任务状态
- `GET /download/<filename>`：下载输出文件

## 技术栈

- 后端：Flask
- 矢量化引擎：vtracer
- 图像处理：Pillow、OpenCV
- 质量评估：scikit-image
- SVG 处理：CairoSVG、svglib、svgelements
- Office 兼容导出：Inkscape（可选）

## 目录结构

```text
.
├── app.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── templates/
├── uploads/
├── outputs/
└── assets/
    └── readme/
```

## 注意事项

- PowerPoint 对 SVG / EMF 的支持会因版本、平台和 Office 渲染差异而有所不同。
- 本项目的目标是让输出**更适合** PowerPoint 导入和后续处理，但无法对所有 Office 版本做绝对保证。
- 如果你主要面向 Windows Office，且环境里有 Inkscape，通常优先尝试 EMF 会更稳。

## 致谢

- [vtracer](https://github.com/visioncortex/vtracer)
- [Flask](https://flask.palletsprojects.com/)
- [scikit-image](https://scikit-image.org/)
- [CairoSVG](https://cairosvg.org/)

## License

[MIT](LICENSE)
