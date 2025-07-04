"""
坐标转换工具 - 处理不同分辨率之间的坐标转换
"""

from typing import List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

class CoordinateConverter:
    """坐标转换器，处理图片坐标到屏幕坐标的转换"""
    
    def __init__(self, image_size: Tuple[int, int], screen_size: Tuple[int, int]):
        """
        初始化坐标转换器
        
        Args:
            image_size: 图片尺寸 (width, height)
            screen_size: 屏幕尺寸 (width, height)
        """
        self.image_width, self.image_height = image_size
        self.screen_width, self.screen_height = screen_size
        
        self.scale_x = self.screen_width / self.image_width
        self.scale_y = self.screen_height / self.image_height
        
        logger.info(f"坐标转换器初始化: 图片({self.image_width}x{self.image_height}) -> 屏幕({self.screen_width}x{self.screen_height})")
        logger.info(f"缩放比例: X={self.scale_x:.3f}, Y={self.scale_y:.3f}")
    
    def convert_point(self, x: float, y: float) -> Tuple[int, int]:
        """
        转换单个点坐标
        
        Args:
            x: 图片坐标X
            y: 图片坐标Y
            
        Returns:
            Tuple[int, int]: 屏幕坐标 (x, y)
        """
        screen_x = int(x * self.scale_x)
        screen_y = int(y * self.scale_y)
        return screen_x, screen_y
    
    def convert_bbox(self, bbox: List[float]) -> List[int]:
        """
        转换边界框坐标
        
        Args:
            bbox: 边界框 [x1, y1, x2, y2]
            
        Returns:
            List[int]: 转换后的边界框坐标
        """
        if len(bbox) != 4:
            raise ValueError("边界框必须包含4个坐标值")
        
        x1, y1, x2, y2 = bbox
        screen_x1, screen_y1 = self.convert_point(x1, y1)
        screen_x2, screen_y2 = self.convert_point(x2, y2)
        
        return [screen_x1, screen_y1, screen_x2, screen_y2]
    
    def convert_center_point(self, bbox: List[float]) -> Tuple[int, int]:
        """
        从边界框计算中心点并转换坐标
        
        Args:
            bbox: 边界框 [x1, y1, x2, y2]
            
        Returns:
            Tuple[int, int]: 屏幕坐标中心点 (x, y)
        """
        if len(bbox) != 4:
            raise ValueError("边界框必须包含4个坐标值")
        
        x1, y1, x2, y2 = bbox
        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2
        
        return self.convert_point(center_x, center_y)
    
    def convert_relative_to_absolute(self, relative_bbox: List[float]) -> List[int]:
        """
        将相对坐标转换为绝对屏幕坐标
        
        Args:
            relative_bbox: 相对坐标 [x1, y1, x2, y2] (0-1范围)
            
        Returns:
            List[int]: 绝对屏幕坐标
        """
        if len(relative_bbox) != 4:
            raise ValueError("相对坐标必须包含4个值")
        
        x1, y1, x2, y2 = relative_bbox
        
        # 转换为图片像素坐标，然后缩放到屏幕坐标
        screen_coords = [
            int(x1 * self.image_width * self.scale_x),
            int(y1 * self.image_height * self.scale_y),
            int(x2 * self.image_width * self.scale_x),
            int(y2 * self.image_height * self.scale_y)
        ]
        
        return screen_coords
    
    def is_conversion_needed(self) -> bool:
        """
        检查是否需要进行坐标转换
        
        Returns:
            bool: 如果图片尺寸和屏幕尺寸不同则返回True
        """
        return (self.image_width != self.screen_width or 
                self.image_height != self.screen_height)
    
    def get_scaling_info(self) -> dict:
        """
        获取缩放信息
        
        Returns:
            dict: 包含缩放比例和尺寸信息的字典
        """
        return {
            'image_size': (self.image_width, self.image_height),
            'screen_size': (self.screen_width, self.screen_height),
            'scale_x': self.scale_x,
            'scale_y': self.scale_y,
            'conversion_needed': self.is_conversion_needed()
        }