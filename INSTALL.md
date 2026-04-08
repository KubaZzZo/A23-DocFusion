# DocFusion 安装说明

## 一、Python 依赖安装

```bash
pip install -r requirements.txt
```

## 二、Tesseract-OCR 安装（OCR功能必需）

### Windows 安装步骤

1. 下载安装包：https://github.com/UB-Mannheim/tesseract/wiki
   - 选择 `tesseract-ocr-w64-setup-5.x.x.exe`（64位）

2. 安装时勾选中文语言包：
   - 安装界面 → Additional language data → 勾选 `Chinese - Simplified`（chi_sim）
   - 默认安装路径：`C:\Program Files\Tesseract-OCR\`

3. 验证安装：
   ```bash
   "C:\Program Files\Tesseract-OCR\tesseract.exe" --version
   ```

### 配置说明

如果 Tesseract 安装在非默认路径，修改 `config.py` 中的 `OCR_CONFIG`：

```python
OCR_CONFIG = {
    "tesseract_cmd": r"D:\你的路径\Tesseract-OCR\tesseract.exe",
    "lang": "chi_sim+eng",
}
```

或设置环境变量：
```bash
set TESSERACT_CMD=D:\你的路径\Tesseract-OCR\tesseract.exe
```

## 三、Ollama 安装（本地LLM可选）

1. 下载：https://ollama.com/download
2. 安装后拉取模型：
   ```bash
   ollama pull qwen2.5:7b
   ```
3. 验证运行：
   ```bash
   ollama list
   ```

## 四、启动应用

```bash
python main.py
```

应用启动后会同时运行 API 服务：http://127.0.0.1:8000/docs
