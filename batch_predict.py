print("--- batch_predict.py 腳本開始執行 ---")

import requests
import os
import glob
import pandas as pd
import time
from typing import List, Dict, Any

# API 端點 URL (假設 API 運行在本地的 8000 port)
API_URL_SINGLE = "http://localhost:8000/predict"
API_URL_BATCH = "http://localhost:8000/predict_batch"  # Bonus: 批次端點
TEST_IMAGE_DIR = "test_images"  # 存放測試圖片的目錄
OUTPUT_CSV = "result.csv"
USE_BATCH_ENDPOINT = True  # 設為 True 以使用 /predict_batch 端點


def predict_single_image_from_path(image_path: str, session: requests.Session) -> Dict[str, Any]:
    """使用 /predict 端點預測單張圖片"""
    try:
        with open(image_path, 'rb') as f:
            files = {'file': (os.path.basename(image_path), f, 'image/png')}  # 假設是 png
            response = session.post(API_URL_SINGLE, files=files, timeout=20)  # 增加 timeout
            response.raise_for_status()  # 如果 HTTP 狀態碼是 4xx 或 5xx，則引發異常
            return response.json()
    except requests.exceptions.RequestException as e:
        print(f"請求錯誤 (單張圖片 {os.path.basename(image_path)}): {e}")
        return {"filename": os.path.basename(image_path), "error": str(e)}
    except Exception as e:
        print(f"預料外的錯誤 (單張圖片 {os.path.basename(image_path)}): {e}")
        return {"filename": os.path.basename(image_path), "error": f"Unexpected error: {str(e)}"}


def predict_multiple_images_via_batch_endpoint(image_paths: List[str], session: requests.Session) -> List[
    Dict[str, Any]]:
    """使用 /predict_batch 端點預測多張圖片"""
    files_to_upload = []
    for image_path in image_paths:
        try:
            # 'files' 參數期望的是 (filename, file_object, content_type) 的元組列表
            files_to_upload.append(('files', (os.path.basename(image_path), open(image_path, 'rb'), 'image/png')))
        except FileNotFoundError:
            print(f"檔案未找到，跳過: {image_path}")
            # 記錄錯誤以便最終報告
            # 這裡直接跳過，API 端會處理不存在的檔案（雖然此腳本是客戶端）
            # 更好的做法是在這裡就產生一個錯誤記錄
            return [{"filename": os.path.basename(image_path), "error": "File not found locally before sending."}]

    if not files_to_upload:
        return []

    try:
        response = session.post(API_URL_BATCH, files=files_to_upload, timeout=60)  # 批次處理可能需要更長 timeout
        response.raise_for_status()
        # 關閉已開啟的檔案物件
        for _, file_tuple in files_to_upload:
            file_tuple[1].close()
        return response.json().get("predictions", [])  # API 回傳 {"predictions": [...]}
    except requests.exceptions.RequestException as e:
        print(f"請求錯誤 (批次): {e}")
        # 關閉已開啟的檔案物件
        for _, file_tuple in files_to_upload:
            file_tuple[1].close()
        # 為所有嘗試上傳的檔案產生錯誤回報
        return [{"filename": os.path.basename(fp), "error": str(e)} for fp in image_paths]
    except Exception as e:
        print(f"預料外的錯誤 (批次): {e}")
        for _, file_tuple in files_to_upload:
            file_tuple[1].close()
        return [{"filename": os.path.basename(fp), "error": f"Unexpected error: {str(e)}"} for fp in image_paths]


def main():
    # 找出 test_images 目錄下所有的 .png 和 .jpg 圖片
    image_paths = glob.glob(os.path.join(TEST_IMAGE_DIR, "*.png")) + \
                  glob.glob(os.path.join(TEST_IMAGE_DIR, "*.jpg")) + \
                  glob.glob(os.path.join(TEST_IMAGE_DIR, "*.jpeg"))

    if not image_paths:
        print(f"在 '{TEST_IMAGE_DIR}' 目錄下未找到任何圖片檔案。")
        return

    print(f"找到 {len(image_paths)} 張圖片準備進行預測。")
    all_results = []
    start_time = time.time()

    with requests.Session() as session:  # 使用 Session 以重用 TCP 連線
        if USE_BATCH_ENDPOINT:
            print(f"使用 /predict_batch 端點進行批次預測...")
            # 可以分批次提交，避免一次提交過多檔案導致請求過大或超時
            batch_size = 10  # 例如一次處理 10 張
            for i in range(0, len(image_paths), batch_size):
                batch_paths = image_paths[i:i + batch_size]
                print(f"  處理批次 {i // batch_size + 1} (共 {len(batch_paths)} 張圖片)...")
                batch_api_results = predict_multiple_images_via_batch_endpoint(batch_paths, session)
                all_results.extend(batch_api_results)
                time.sleep(0.1)  # 短暫停頓，避免請求過於頻繁 (可選)
        else:
            print(f"使用 /predict 端點逐張預測...")
            for i, image_path in enumerate(image_paths):
                print(f"  正在預測圖片: {os.path.basename(image_path)} ({i + 1}/{len(image_paths)})")
                result = predict_single_image_from_path(image_path, session)
                all_results.append(result)
                time.sleep(0.1)  # 短暫停頓

    end_time = time.time()
    print(f"所有圖片預測完成，總耗時: {end_time - start_time:.2f} 秒。")

    # 將結果轉換為 DataFrame 並儲存為 CSV
    if all_results:
        df = pd.DataFrame(all_results)
        # 確保 'filename' 和 'predicted_class' 或 'error' 欄位存在
        if 'predicted_class' not in df.columns and 'error' in df.columns:
            df['predicted_class'] = None  # 如果只有錯誤，則預測類別為空
        elif 'error' not in df.columns and 'predicted_class' in df.columns:
            df['error'] = None  # 如果只有成功，則錯誤為空
        elif 'error' not in df.columns and 'predicted_class' not in df.columns and all_results:
            # 處理完全空的 response 或非預期格式
            print("警告: API 回應的格式非預期，結果可能不完整。")

        # 重新排列欄位順序，讓 filename 在前面
        cols = ['filename']
        if 'predicted_class' in df.columns:
            cols.append('predicted_class')
        if 'error' in df.columns:
            cols.append('error')

        # 過濾掉 df.columns 中不存在的欄位
        final_cols = [col for col in cols if col in df.columns]

        if final_cols:
            df = df[final_cols]
            df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')  # utf-8-sig 確保 Excel 能正確顯示中文
            print(f"預測結果已儲存到 '{OUTPUT_CSV}'")
        else:
            print("沒有可寫入的欄位，CSV 檔案未產生。")

    else:
        print("沒有收到任何預測結果。")


if __name__ == "__main__":
    main()