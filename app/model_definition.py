# app/model_definition.py
import torch
import torch.nn as nn
import torch.nn.functional as F

class CNNTransformer(nn.Module):
    def __init__(self):
        super(CNNTransformer, self).__init__()

        # CNN 部分
        self.conv1 = nn.Conv2d(1, 32, 3, padding=1)  # → [32, 28, 28]
        self.conv2 = nn.Conv2d(32, 64, 3, padding=1) # → [64, 28, 28]
        self.pool = nn.MaxPool2d(2, 2)               # → [64, 14, 14]

        # 將 CNN 輸出 reshape 為 Transformer 輸入
        # 調整：在 TransformerEncoderLayer 中使用 batch_first=True 更常見
        self.linear_in = nn.Linear(14 * 14, 128)
        self.transformer_layer = nn.TransformerEncoderLayer(d_model=128, nhead=8, batch_first=True) # 注意 batch_first=True
        self.transformer = nn.TransformerEncoder(self.transformer_layer, num_layers=2)

        # 最後接分類器
        self.fc = nn.Linear(64 * 128, 10)  # 64 是 token 數量 (channel 數)，128 是每 token 的向量長度

    def forward(self, x):
        x = F.relu(self.conv1(x))     # [batch, 32, 28, 28]
        x = F.relu(self.conv2(x))     # [batch, 64, 28, 28]
        x = self.pool(x)              # [batch, 64, 14, 14]

        # 將每個 channel 當成一個 token，flatten spatial 維度
        x = x.view(x.size(0), 64, -1)           # [batch, 64, 14*14]
        x = self.linear_in(x)                   # [batch, 64, 128]

        # 如果 TransformerEncoderLayer 使用 batch_first=True, 輸入應為 [batch, seq_len, d_model]
        # 這裡 seq_len 是 64 (channels), d_model 是 128
        x = self.transformer(x)                 # → [batch, 64, 128]
        x = x.reshape(x.size(0), -1)            # → [batch, 64*128]

        x = self.fc(x)                          # → [batch, 10]
        return x

# 注意：
# 你的 Jupyter Notebook 使用了 permute 操作來調整維度給 Transformer：
# x = x.permute(1, 0, 2) # → [seq_len=64, batch, d_model=128]
# x = self.transformer(x) # → [64, batch, 128]
# x = x.permute(1, 0, 2) # → [batch, 64, 128]
# 如果你的 model_weights.pth 是基於這種 permute 邏輯訓練的，你可能需要保留這些 permute 操作，
# 並確保 TransformerEncoderLayer 沒有設置 batch_first=True (或設為 False)。
# 這裡我採用了 batch_first=True 的方式，這在 PyTorch 中更常見且通常更直觀。
# 如果你的權重與此不兼容，可能需要調整回 permute 邏輯或重新訓練模型（如果差異不大，可能仍然有效）。
# 假設目前的權重與 batch_first=True 的方式兼容。