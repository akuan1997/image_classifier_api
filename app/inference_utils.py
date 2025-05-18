# app/inference_utils.py
import torch
from torchvision import transforms
from PIL import Image, UnidentifiedImageError
import io
import os
from .model_definition import CNNTransformer # 相對導入

# 模型權重路徑，根據 Dockerfile 中的 COPY 指令，它會被放在 /app 目錄下
# 或者如果在本機運行 uvicorn (從專案根目錄)，則是相對於根目錄
MODEL_FILENAME = "model_weights.pth"
MODEL_PATH_DOCKER = f"/app/{MODEL_FILENAME}"
MODEL_PATH_LOCAL = MODEL_FILENAME

DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# 載入模型函式
def load_model():
    model = CNNTransformer()
    model_path_to_try = MODEL_PATH_LOCAL
    if os.path.exists(MODEL_PATH_DOCKER): # 優先 Docker 環境中的路徑
        model_path_to_try = MODEL_PATH_DOCKER
    elif not os.path.exists(MODEL_PATH_LOCAL) and not os.path.exists(MODEL_PATH_DOCKER):
         # 嘗試相對於此 utils 檔案的路徑 (如果直接執行此檔案或從 app 目錄執行)
        script_dir = os.path.dirname(__file__)
        model_path_project_root_style = os.path.join(os.path.dirname(script_dir), MODEL_FILENAME)
        if os.path.exists(model_path_project_root_style):
            model_path_to_try = model_path_project_root_style
        else:
            raise RuntimeError(f"Model weights not found. Tried: {MODEL_PATH_DOCKER}, {MODEL_PATH_LOCAL}, {model_path_project_root_style}")

    print(f"Loading model from: {model_path_to_try} onto device: {DEVICE}")
    model.load_state_dict(torch.load(model_path_to_try, map_location=DEVICE))
    model.to(DEVICE)
    model.eval()
    return model

model = load_model()

# 定義圖片轉換
# 確保與訓練時的預處理一致
transform = transforms.Compose([
    transforms.Resize((28, 28)),
    transforms.Grayscale(num_output_channels=1), # 確保是單通道灰階
    transforms.ToTensor(),                       # 將圖片轉為 Tensor，並將像素值縮放到 [0, 1]
    # transforms.Normalize((0.5,), (0.5,)) # 如果訓練時有做 Normalize，這裡也要加上
])

def preprocess_image_bytes(image_bytes: bytes) -> torch.Tensor:
    """將圖片的 bytes 轉換為模型可接受的 Tensor"""
    try:
        image = Image.open(io.BytesIO(image_bytes))
    except UnidentifiedImageError:
        raise ValueError("Cannot identify image file. It might be corrupted or not an image.")
    # 確保轉換後的圖片是 L (灰階) 模式，如果原始圖片是 RGBA 或其他
    if image.mode != 'L':
        image = image.convert('L')
    return transform(image).unsqueeze(0) # 增加 batch 維度 [1, 1, 28, 28]

def predict_single_image(image_tensor: torch.Tensor) -> int:
    """對單張預處理過的圖片 Tensor 進行預測"""
    with torch.no_grad():
        output = model(image_tensor.to(DEVICE)) # 將 tensor 送到正確的 device
        _, pred = torch.max(output, 1)
        return pred.item()

def predict_image_batch(image_tensors: list[torch.Tensor]) -> list[int]:
    """對一批預處理過的圖片 Tensors 進行預測"""
    if not image_tensors:
        return []
    # 將 list of tensors (每個 shape [1, C, H, W]) 合併成一個 batch tensor ([N, C, H, W])
    batch_tensor = torch.cat(image_tensors, dim=0).to(DEVICE)
    with torch.no_grad():
        outputs = model(batch_tensor)
        _, preds = torch.max(outputs, 1)
        return preds.cpu().tolist() # 將結果轉為 list of integers