"""
简化的OmniParser实现 - 只包含核心功能，减少依赖
"""

import torch
from PIL import Image
import io
import base64
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class SimpleOmniParser:
    """简化的OmniParser类，模拟屏幕元素检测功能"""
    
    def __init__(self, config: Optional[Dict] = None):
        """
        初始化简化的OmniParser
        
        Args:
            config: 配置字典
        """
        self.config = config or {}
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        logger.info(f"SimpleOmniParser initialized on {self.device}")
    
    def parse(self, image_base64: str) -> Tuple[str, List[Dict]]:
        """
        解析屏幕截图，模拟检测UI元素
        
        Args:
            image_base64: Base64编码的图像数据
            
        Returns:
            Tuple[str, List[Dict]]: (原始图像base64, 模拟的元素列表)
        """
        try:
            # 解码图像
            image_bytes = base64.b64decode(image_base64)
            image = Image.open(io.BytesIO(image_bytes))
            
            logger.info(f"Processing image of size: {image.size}")
            
            # 模拟屏幕元素检测
            parsed_content_list = self._simulate_screen_elements(image)
            
            # 返回原始图像（在实际实现中这里会是标注后的图像）
            return image_base64, parsed_content_list
            
        except Exception as e:
            logger.error(f"Failed to parse screen: {str(e)}")
            raise
    
    def _simulate_screen_elements(self, image: Image.Image) -> List[Dict]:
        """
        模拟屏幕元素检测
        
        Args:
            image: PIL图像对象
            
        Returns:
            List[Dict]: 模拟的UI元素列表
        """
        width, height = image.size
        
        # 模拟检测到的元素
        elements = [
            {
                'id': 0,
                'type': 'button',
                'description': 'Start button',
                'coordinates': [50, height-50, 150, height-20],
                'text': 'Start',
                'confidence': 0.9
            },
            {
                'id': 1,
                'type': 'window',
                'description': 'Main window',
                'coordinates': [100, 100, width-100, height-150],
                'text': '',
                'confidence': 0.8
            },
            {
                'id': 2,
                'type': 'icon',
                'description': 'Calculator icon',
                'coordinates': [200, 200, 250, 250],
                'text': 'Calculator',
                'confidence': 0.7
            },
            {
                'id': 3,
                'type': 'text',
                'description': 'Text field',
                'coordinates': [300, 150, 500, 180],
                'text': 'Type here...',
                'confidence': 0.85
            }
        ]
        
        logger.debug(f"Simulated {len(elements)} UI elements")
        return elements