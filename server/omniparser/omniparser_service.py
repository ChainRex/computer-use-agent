"""
OmniParser服务 - 封装OmniParser功能用于屏幕元素检测
"""

import torch
from PIL import Image
import io
import base64
from typing import Dict, List, Optional, Tuple
try:
    from .omniparser import Omniparser
    FULL_OMNIPARSER_AVAILABLE = True
except ImportError as e:
    print(f"Full OmniParser not available: {e}")
    from .simple_omniparser import SimpleOmniParser as Omniparser
    FULL_OMNIPARSER_AVAILABLE = False
import logging

logger = logging.getLogger(__name__)

class OmniParserService:
    """OmniParser服务类，提供屏幕元素检测功能"""
    
    def __init__(self, config: Optional[Dict] = None):
        """
        初始化OmniParser服务
        
        Args:
            config: 配置字典，包含模型路径等信息
        """
        if config is None:
            config = self._get_default_config()
        
        self.config = config
        self.omniparser = None
        self._initialize_parser()
    
    def _get_default_config(self) -> Dict:
        """获取默认配置"""
        import os
        # 获取服务端目录的绝对路径
        server_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return {
            'som_model_path': os.path.join(server_dir, 'weights/icon_detect/model.pt'),
            'caption_model_name': 'florence2',
            'caption_model_path': '/root/autodl-tmp/OmniParser/microsoft/Florence-2-base-ft',  # 使用本地路径
            'processor_path': '/root/autodl-tmp/OmniParser/microsoft/Florence-2-base-ft',   # 使用本地路径
            'BOX_TRESHOLD': 0.05
        }
    
    def _initialize_parser(self):
        """初始化OmniParser"""
        try:
            self.omniparser = Omniparser(self.config)
            logger.info("OmniParser initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize OmniParser: {str(e)}")
            raise
    
    def parse_screen(self, image_base64: str) -> Tuple[str, List[Dict]]:
        """
        解析屏幕截图，检测UI元素
        
        Args:
            image_base64: Base64编码的图像数据
            
        Returns:
            Tuple[str, List[Dict]]: (标注后的图像base64, 检测到的元素列表)
        """
        if not self.omniparser:
            raise RuntimeError("OmniParser not initialized")
        
        try:
            # 调用OmniParser进行解析
            labeled_img_base64, parsed_content_list = self.omniparser.parse(image_base64)
            
            # 格式化输出
            formatted_elements = self._format_parsed_content(parsed_content_list)
            
            logger.debug(f"Parsed {len(formatted_elements)} elements from screen")
            
            return labeled_img_base64, formatted_elements
            
        except Exception as e:
            logger.error(f"Failed to parse screen: {str(e)}")
            raise
    
    def _format_parsed_content(self, parsed_content_list: List) -> List[Dict]:
        """
        格式化解析后的内容
        
        Args:
            parsed_content_list: OmniParser输出的原始内容列表
            
        Returns:
            List[Dict]: 格式化后的元素列表
        """
        formatted_elements = []
        
        for i, content in enumerate(parsed_content_list):
            if isinstance(content, dict):
                element = {
                    'id': i,
                    'type': content.get('type', 'unknown'),
                    'description': content.get('description', ''),
                    'coordinates': content.get('coordinates', []),
                    'text': content.get('text', ''),
                    'confidence': content.get('confidence', 0.0)
                }
            else:
                # 处理其他格式的内容
                element = {
                    'id': i,
                    'type': 'element',
                    'description': str(content),
                    'coordinates': [],
                    'text': '',
                    'confidence': 0.0
                }
            
            formatted_elements.append(element)
        
        return formatted_elements
    
    def is_available(self) -> bool:
        """检查OmniParser是否可用"""
        return self.omniparser is not None
    
    def get_status(self) -> Dict:
        """获取服务状态"""
        return {
            'available': self.is_available(),
            'device': 'cuda' if torch.cuda.is_available() else 'cpu',
            'models_loaded': self.omniparser is not None,
            'full_omniparser': FULL_OMNIPARSER_AVAILABLE,
            'mode': 'full' if FULL_OMNIPARSER_AVAILABLE else 'simulation'
        }