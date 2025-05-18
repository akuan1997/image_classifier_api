
from fastapi import FastAPI, File, UploadFile, HTTPException, status
from fastapi.responses import JSONResponse
import logging
from typing import List, Dict, Any
from .inference_utils import preprocess_image_bytes, predict_single_image, predict_image_batch, DEVICE
from PIL import UnidentifiedImageError # 確保導入
import torch

app = FastAPI(
    title="數字圖片分類 API",
    description="一個使用 CNN-Transformer 模型來分類手寫數字圖片的 API。",
    version="1.0.0",
    contact={
        "name": "API 開發者",
        "url": "http://example.com/contact", # 替換成你的資訊
        "email": "developer@example.com",    # 替換成你的資訊
    },
    license_info={
        "name": "Apache 2.0", # 或其他你選擇的授權
        "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
    },
)

# 設定日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

logger.info(f"應用程式啟動中。使用的運算裝置: {DEVICE}")

@app.on_event("startup")
async def startup_event():
    # 可以在此處預載入模型或執行暖身 (warm-up) 推論
    # inference_utils 中模型已經在模組載入時載入
    logger.info("模型已載入，API 準備好接收請求。")
    try:
        # 執行一次 dummy 推論來暖身 (可選)
        dummy_tensor = torch.randn(1, 1, 28, 28).to(DEVICE)
        _ = predict_single_image(dummy_tensor) # 使用 predict_single_image 而不是 model() 直接調用
        logger.info("模型暖身完成。")
    except Exception as e:
        logger.warning(f"模型暖身時發生錯誤: {e}")


@app.post("/predict",
            summary="預測單張圖片的數字類別",
            response_description="包含檔名和預測類別的 JSON 物件")
async def predict_single_endpoint(file: UploadFile = File(..., description="要進行分類的圖片檔案 (PNG, JPG等)")):
    """
    上傳一張圖片檔案，API 將回傳預測的數字類別。

    - **file**: 圖片檔案。
    """
    try:
        image_bytes = await file.read()
        image_tensor = preprocess_image_bytes(image_bytes)
    except ValueError as e: # 由 preprocess_image_bytes 引發
        logger.error(f"處理圖片 {file.filename} 時發生 ValueError: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"處理圖片 {file.filename} 時發生未預期錯誤: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"處理圖片時發生錯誤: {str(e)}")

    try:
        prediction = predict_single_image(image_tensor)
        logger.info(f"檔案 {file.filename} 的預測結果: {prediction}")
        return JSONResponse(content={"filename": file.filename, "predicted_class": prediction})
    except Exception as e:
        logger.error(f"對圖片 {file.filename} 進行推論時發生錯誤: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"模型推論時發生錯誤: {str(e)}")


# Bonus: /predict_batch 端點
@app.post("/predict_batch",
            summary="預測多張圖片的數字類別 (批次處理)",
            response_description="包含每張圖片檔名和其對應預測類別的列表")
async def predict_batch_endpoint(files: List[UploadFile] = File(..., description="要進行分類的多個圖片檔案")):
    """
    上傳多張圖片檔案，API 將回傳每張圖片的預測數字類別。
    如果某個檔案處理失敗，會在該檔案的結果中註明錯誤。
    """
    results: List[Dict[str, Any]] = []
    image_tensors_to_process: List[torch.Tensor] = []
    processed_filenames: List[str] = [] # 記錄成功預處理的檔案名稱順序

    for file in files:
        try:
            image_bytes = await file.read()
            image_tensor = preprocess_image_bytes(image_bytes) # 已經包含 batch 維度
            image_tensors_to_process.append(image_tensor)
            processed_filenames.append(file.filename) # 記錄檔名
        except ValueError as e:
            logger.warning(f"批次處理中，跳過無效圖片檔案 {file.filename}: {e}")
            results.append({"filename": file.filename, "error": str(e)})
        except Exception as e:
            logger.warning(f"批次處理中，跳過檔案 {file.filename}，因處理時發生錯誤: {e}")
            results.append({"filename": file.filename, "error": f"處理時發生錯誤: {str(e)}"})

    if not image_tensors_to_process: # 如果沒有任何圖片成功預處理
        if results: # 但有錯誤記錄
             return JSONResponse(content={"predictions": results, "detail": "所有提供的圖片都無法處理。"})
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="未提供有效的圖片檔案進行批次預測。")

    try:
        batch_predictions = predict_image_batch(image_tensors_to_process) # 傳遞 tensors list
    except Exception as e:
        logger.error(f"批次推論時發生錯誤: {e}")
        # 為所有成功預處理的圖片標記推論錯誤
        for fname in processed_filenames:
            # 檢查是否已經有預處理錯誤
            if not any(r['filename'] == fname and 'error' in r for r in results):
                results.append({"filename": fname, "error": f"模型批次推論時發生錯誤: {str(e)}"})
        return JSONResponse(content={"predictions": results, "detail": "模型批次推論時發生錯誤。"}, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


    # 將成功預測的結果與之前可能發生的預處理錯誤合併
    # 按照 processed_filenames 的順序來匹配預測結果
    temp_prediction_map = {filename: pred for filename, pred in zip(processed_filenames, batch_predictions)}

    final_results: List[Dict[str, Any]] = []
    for original_file in files: # 遍歷原始上傳的檔案列表以保持順序
        fname = original_file.filename
        # 檢查是否有預處理錯誤
        error_entry = next((r for r in results if r["filename"] == fname and "error" in r), None)
        if error_entry:
            final_results.append(error_entry)
        elif fname in temp_prediction_map: # 如果沒有預處理錯誤且有預測結果
            final_results.append({"filename": fname, "predicted_class": temp_prediction_map[fname]})
        # else: # 理論上不應該發生，除非邏輯有誤
            # final_results.append({"filename": fname, "error": "未知狀態，未找到預測結果或錯誤"})

    logger.info(f"批次預測處理了 {len(processed_filenames)} 張圖片 (共 {len(files)} 張)。")
    return JSONResponse(content={"predictions": final_results})


@app.get("/", include_in_schema=False) #不在 OpenAPI 文件中顯示
async def root():
    return {"message": "數字圖片分類 API 已啟動。請前往 /docs 查看 API 文件。"}

# 若直接執行此檔案 (用於開發測試，非生產環境建議)
if __name__ == "__main__":
    import uvicorn
    # 注意：直接運行時，模型路徑可能需要調整，
    # inference_utils.py 中的 load_model() 已嘗試處理此情況
    uvicorn.run(app, host="0.0.0.0", port=8000)