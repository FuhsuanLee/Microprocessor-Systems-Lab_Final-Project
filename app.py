#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FastAPI 圖片辨識服務
接收 Base64 圖片並使用 MediaPipe 進行手勢辨識
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import base64
import numpy as np
import cv2

def is_green_image(img):
    """偵測圖片是否為綠色"""
    # 轉換顏色空間 BGR -> HSV
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    
    # 定義綠色範圍 (OpenCV H: 0-180)
    lower_green = np.array([35, 43, 46])
    upper_green = np.array([77, 255, 255])
    
    # 產生遮罩
    mask = cv2.inRange(hsv, lower_green, upper_green)
    
    # 計算綠色像素比例
    green_pixels = cv2.countNonZero(mask)
    total_pixels = img.shape[0] * img.shape[1]
    print(f"Green pixels: {green_pixels}, Total pixels: {total_pixels}, Ratio: {green_pixels / total_pixels}")
    # 如果綠色像素超過 5% 認定為是綠色
    return (green_pixels / total_pixels) > 0.8

app = FastAPI(title="綠色辨識 API")

class ImageRequest(BaseModel):
    image_base64: str


@app.get("/")
async def root():
    """API 首頁"""
    return {
        "message": "綠色辨識 API",
        "endpoint": "POST /detect - 接收 Base64 圖片進行辨識"
    }


@app.post("/detect")
async def detect(request: ImageRequest):
    """
    接收 Base64 編碼圖片進行綠色辨識
    
    Args:
        request: 包含 image_base64 字串的 JSON 物件
    
    Returns:
        result: True=偵測到綠色, False=未偵測到綠色
        message: 辨識結果訊息
    """
    try:
        # 移除可能的 header (例如 "data:image/jpeg;base64,")
        if "," in request.image_base64:
            encoded_data = request.image_base64.split(",", 1)[1]
        else:
            encoded_data = request.image_base64
            
        # 解碼 Base64
        try:
            image_data = base64.b64decode(encoded_data)
        except Exception:
            raise HTTPException(status_code=400, detail="無效的 Base64 字串")

        # 轉換為 numpy array
        nparr = np.frombuffer(image_data, np.uint8)
        
        # 解碼為 OpenCV 圖片
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        print(img)
        
        if img is None:
            raise HTTPException(status_code=400, detail="無法解析圖片資料")

        # 辨識是否為綠色
        is_green = is_green_image(img)
        
        # 根據結果產生訊息
        if is_green:
            message = "偵測到綠色"
        else:
            message = "未偵測到綠色"
        return {
            "result": is_green,
            "message": message
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"辨識失敗: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
