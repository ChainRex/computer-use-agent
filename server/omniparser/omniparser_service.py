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
            'caption_model_path': '/root/autodl-tmp/computer-use-agent/server/weights/icon_caption_florence',  # 使用本地路径
            'processor_path': '/root/autodl-tmp/computer-use-agent/server/weights/Florence-2-base-ft',   # 使用本地路径
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
    
    def parse_screen(self, image_base64: str, screen_resolution: Optional[Tuple[int, int]] = None) -> Tuple[str, List[Dict]]:
        """
        解析屏幕截图，检测UI元素
        
        Args:
            image_base64: Base64编码的图像数据
            screen_resolution: 实际屏幕分辨率 (width, height), 如果提供则用于坐标转换
            
        Returns:
            Tuple[str, List[Dict]]: (标注后的图像base64, 检测到的元素列表)
        """
        if not self.omniparser:
            raise RuntimeError("OmniParser not initialized")
        
        try:
            # 获取图片尺寸信息
            import base64
            import io
            from PIL import Image
            image_data = base64.b64decode(image_base64)
            image = Image.open(io.BytesIO(image_data))
            image_size = image.size  # (width, height)
            
            # 调用OmniParser进行解析
            labeled_img_base64, parsed_content_list = self.omniparser.parse(image_base64)
            
            # 打印调试信息，查看原始数据结构
            logger.info(f"Raw parsed_content_list sample: {parsed_content_list[:3] if parsed_content_list else 'Empty'}")
            
            # 格式化输出，如果提供了屏幕分辨率则使用，否则使用图片尺寸
            target_resolution = screen_resolution if screen_resolution else image_size
            formatted_elements = self._format_parsed_content(parsed_content_list, image_size, target_resolution)
            
            logger.debug(f"Parsed {len(formatted_elements)} elements from screen")
            
            return labeled_img_base64, formatted_elements
            
        except Exception as e:
            logger.error(f"Failed to parse screen: {str(e)}")
            raise
    
    def _format_parsed_content(self, parsed_content_list: List, image_size: Tuple[int, int] = (1280, 720), target_resolution: Optional[Tuple[int, int]] = None) -> List[Dict]:
        """
        格式化解析后的内容
        
        Args:
            parsed_content_list: OmniParser输出的原始内容列表
            image_size: 图片尺寸 (width, height)
            target_resolution: 目标分辨率 (width, height), 如果提供则进行坐标转换
            
        Returns:
            List[Dict]: 格式化后的元素列表
        """
        formatted_elements = []
        image_width, image_height = image_size
        
        # 如果提供了目标分辨率，计算缩放比例
        if target_resolution:
            target_width, target_height = target_resolution
            scale_x = target_width / image_width
            scale_y = target_height / image_height
            logger.info(f"Coordinate scaling: image({image_width}x{image_height}) -> screen({target_width}x{target_height}), scale({scale_x:.3f}, {scale_y:.3f})")
        else:
            scale_x = scale_y = 1.0
            target_width, target_height = image_width, image_height
        
        for i, content in enumerate(parsed_content_list):
            if isinstance(content, dict):
                # 从OmniParser的输出格式提取信息
                bbox = content.get('bbox', [])
                content_text = content.get('content', '')
                element_type = content.get('type', 'unknown')
                
                # 转换bbox格式 (通常是[x1, y1, x2, y2]的相对坐标)
                if bbox and len(bbox) >= 4:
                    # 首先转换为图片像素坐标，然后缩放到目标分辨率
                    coordinates = [
                        int(bbox[0] * image_width * scale_x),   # x1
                        int(bbox[1] * image_height * scale_y),  # y1  
                        int(bbox[2] * image_width * scale_x),   # x2
                        int(bbox[3] * image_height * scale_y)   # y2
                    ]
                else:
                    coordinates = []
                
                element = {
                    'id': i,
                    'type': element_type,
                    'description': content_text or f'{element_type.title()} element {i}',
                    'coordinates': coordinates,
                    'text': content_text if element_type == 'text' else '',
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