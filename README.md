
## 🚀 快速開始 (使用 Docker - 推薦)

### 前置需求

*   [Docker Desktop](https://www.docker.com/products/docker-desktop/) 或 Docker Engine 已安裝並正在運行。
*   Git (用於 clone 專案)。

### 步驟

1.  **Clone 專案**:
    ```bash
    git clone https://github.com/你的GitHub用戶名/image_classifier_api.git # 替換成你的儲存庫 URL
    cd image_classifier_api
    ```

2.  **取得模型權重 (重要!)**:
    將預訓練的模型權重檔案 `model_weights.pth` 放置到專案的根目錄下。
    *注意：由於模型權重檔案可能較大，通常不建議直接將其推送到 Git 儲存庫。你可以考慮使用 Git LFS (Large File Storage) 或者將其存放在外部儲存 (如 S3, Google Cloud Storage) 並在 `README` 中說明如何下載。如果檔案不大 (例如幾十MB)，直接放入也尚可接受。*

3.  **建立 Docker 映像檔**:
    在專案根目錄下執行：
    ```bash
    docker build -t image-classifier-api .
    ```
    (你可以使用自訂的標籤，例如 `yourname/image-classifier-api:latest`)

4.  **執行 Docker 容器**:
    ```bash
    docker run -d -p 8000:8000 --name my-digit-api image-classifier-api
    ```
    *   `-d`: 在背景執行容器。
    *   `-p 8000:8000`: 將主機的 8000 port 映射到容器的 8000 port。
    *   `--name my-digit-api`: 給容器一個自訂的名稱。

5.  **驗證服務狀態**:
    *   檢查容器是否運行: `docker ps` (你應該會看到 `my-digit-api` 正在運行)
    *   查看容器日誌: `docker logs my-digit-api` (確認服務正常啟動)
    *   在瀏覽器中打開 `http://localhost:8000/docs`，你應該能看到 Swagger UI API 文件。

## 📖 API 使用說明

API 啟動後，可以透過瀏覽器或任何 API 測試工具 (如 Postman, cURL) 存取。

*   **API Base URL**: `http://localhost:8000` (當在本機 Docker 運行時)
*   **Swagger UI (互動式 API 文件)**: `http://localhost:8000/docs`
*   **ReDoc (替代 API 文件)**: `http://localhost:8000/redoc`

### 端點 1: `/predict` (單張圖片預測)

*   **Method**: `POST`
*   **URL**: `/predict`
*   **Content-Type**: `multipart/form-data`
*   **Request Body**:
    *   `file`: (必需) 圖片檔案 (例如 PNG, JPG)。
*   **成功回應 (200 OK)**:
    ```json
    {
      "filename": "test_image.png",
      "predicted_class": 7
    }
    ```
*   **cURL 範例**:
    ```bash
    curl -X POST -F "file=@/path/to/your/image.png" http://localhost:8000/predict
    ```

### 端點 2: `/predict_batch` (批次圖片預測 - Bonus)

*   **Method**: `POST`
*   **URL**: `/predict_batch`
*   **Content-Type**: `multipart/form-data`
*   **Request Body**:
    *   `files`: (必需) 一個或多個圖片檔案。在 Postman 或程式碼中，你需要多次指定 `files` 這個 key，並分別上傳不同的檔案。
*   **成功回應 (200 OK)**:
    ```json
    {
      "predictions": [
        {
          "filename": "image1.png",
          "predicted_class": 3
        },
        {
          "filename": "image2.jpg",
          "predicted_class": 9
        },
        {
          "filename": "corrupted_image.png",
          "error": "Cannot identify image file. It might be corrupted or not an image."
        }
      ]
    }
    ```
*   **cURL 範例**:
    ```bash
    curl -X POST \
      -F "files=@/path/to/image1.png" \
      -F "files=@/path/to/image2.jpg" \
      http://localhost:8000/predict_batch
    ```

## 🧪 執行批次預測腳本 (本地測試)

`batch_predict.py` 腳本可以對 `test_images/` 目錄下的所有圖片進行預測，並將結果輸出到 `result.csv`。

1.  **前置條件**:
    *   API 服務正在運行 (無論是在本機直接運行，還是在 Docker 容器中運行並映射到 `localhost:8000`)。
    *   Python 環境已安裝 `requests` 和 `pandas` (如果使用虛擬環境，確保已啟動)。
    *   `test_images/` 目錄下有範例圖片。

2.  **執行腳本**:
    在專案根目錄下，啟動你的 Python 虛擬環境並執行：
    ```bash
    python batch_predict.py
    ```

3.  **檢查結果**:
    腳本執行完畢後，會在專案根目錄下生成 `result.csv` 檔案。

## 🛠️ 本地開發 (不使用 Docker)

如果你想在本地直接運行 FastAPI 應用程式進行開發或測試：

1.  **Clone 專案** (同上)。
2.  **取得模型權重 `model_weights.pth`** (同上)。
3.  **建立並啟動 Python 虛擬環境**:
    ```bash
    python -m venv .venv
    # Windows:
    .\.venv\Scripts\Activate.ps1
    # macOS/Linux:
    source .venv/bin/activate
    ```
4.  **安裝依賴**:
    ```bash
    pip install -r requirements.txt
    ```
5.  **啟動 FastAPI 開發伺服器**:
    ```bash
    uvicorn app.main:app --reload
    ```
    服務將運行在 `http://localhost:8000`。

## 🧹 清理 Docker 資源

*   停止容器: `docker stop my-digit-api`
*   移除容器: `docker rm my-digit-api`
*   移除映像檔 (可選): `docker rmi image-classifier-api`

## 🤝 貢獻

歡迎提交 Pull Requests 或 Issues 來改進這個專案！

## 📄 授權

此專案採用 [MIT License](LICENSE) (如果你選擇了 MIT 授權，請加入一個 `LICENSE` 檔案)。
