# Dockerfile
# 使用官方 Python 映像檔作為基礎
FROM python:3.9-slim

# 設定工作目錄
WORKDIR /app

# 複製 requirements.txt 並安裝依賴
COPY requirements.txt .
# 為了減小映像檔大小，可以考慮安裝 torch 的 CPU only 版本
# 例如：RUN pip install --no-cache-dir -r requirements.txt torch==<version>+cpu torchvision==<version>+cpu -f https://download.pytorch.org/whl/torch_stable.html
RUN pip install --no-cache-dir -r requirements.txt

# 複製應用程式程式碼到容器中
COPY ./app ./app
# 將模型權重檔案複製到 /app 工作目錄下，這樣 inference_utils.py 就能找到它
COPY model_weights.pth .

# 開放容器的 8000 連接埠
EXPOSE 8000

# 設定環境變數，讓 Python 的輸出直接打印，不進行緩衝
ENV PYTHONUNBUFFERED 1
# (可選) 如果你的 inference_utils.py 需要通過環境變數知道模型路徑
# ENV MODEL_PATH /app/model_weights.pth

# 容器啟動時執行的命令
# 使用 Gunicorn 作為 WSGI 伺服器，並使用 Uvicorn workers 來運行 FastAPI 應用
# -w 4: 啟動 4 個 worker process (通常建議 CPU 核心數 * 2 + 1，但需視情況調整)
# -k uvicorn.workers.UvicornWorker: 指定使用 Uvicorn worker
# app.main:app: 指向 app/main.py 中的 app FastAPI 實例
# --bind 0.0.0.0:8000: 監聽所有網路介面的 8000 port
# --timeout 120: worker 超時時間 (秒)
CMD ["gunicorn", "-w", "2", "-k", "uvicorn.workers.UvicornWorker", "app.main:app", "--bind", "0.0.0.0:8000", "--timeout", "120", "--log-level", "info"]