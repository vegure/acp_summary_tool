import os
import logging
import time
from abc import ABC, abstractmethod
from PIL import Image
import pillow_heif

# 注册HEIC打开器
pillow_heif.register_heif_opener()

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class ImageConverter(ABC):
    """图片转换器抽象基类，定义插件接口"""
    @abstractmethod
    def can_convert(self, file_path: str) -> bool:
        """检查文件是否可以被当前转换器处理"""
        pass

    @abstractmethod
    def convert(self, file_path: str, output_dir: str) -> str:
        """转换图片并返回转换后的文件路径"""
        pass


class HEICToJPEGConverter(ImageConverter):
    """HEIC到JPEG格式的转换器"""
    def can_convert(self, file_path: str) -> bool:
        return file_path.lower().endswith('.heic')

    def convert(self, file_path: str, output_dir: str) -> str:
        try:
            # 读取HEIC图片
            image = Image.open(file_path)
            # 准备输出路径
            file_name = os.path.basename(file_path)
            base_name = os.path.splitext(file_name)[0]
            output_path = os.path.join(output_dir, f"{base_name}.jpeg")
            # 保留EXIF数据
            exif_data = image.info.get('exif', None)
            if exif_data:
                image.save(output_path, 'JPEG', exif=exif_data)
            else:
                image.save(output_path, 'JPEG')
            logging.info(f"已将{file_path}转换为JPEG格式，保存为{output_path}")
            return output_path
        except Exception as e:
            logging.error(f"转换图片{file_path}失败: {e}")
            return None


class ImageProcessor:
    """图像处理类，支持插件式架构"""
    def __init__(self):
        self.converters = []
        # 注册默认转换器
        self.register_converter(HEICToJPEGConverter())

    def register_converter(self, converter: ImageConverter):
        """注册新的图片转换器插件"""
        self.converters.append(converter)
        logging.info(f"已注册图片转换器: {converter.__class__.__name__}")

    def process_image(self, file_path: str, output_dir: str) -> str:
        """处理单张图片，根据文件类型选择合适的转换器"""
        # 如果已经是JPEG格式，直接返回
        if file_path.lower().endswith(('.jpeg', '.jpg')):
            logging.info(f"文件{file_path}已是JPEG格式，无需转换")
            return file_path

        # 尝试使用已注册的转换器
        for converter in self.converters:
            if converter.can_convert(file_path):
                return converter.convert(file_path, output_dir)

        logging.warning(f"没有找到适合处理{file_path}的转换器")
        return None

    def process_directory(self, input_dir: str, output_dir: str = None) -> list[str]:
        """处理目录下的所有图片"""
        # 如果未指定输出目录，则使用输入目录
        if output_dir is None:
            output_dir = input_dir

        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)

        # 遍历目录下的所有文件
        image_files = []
        for file_name in os.listdir(input_dir):
            file_path = os.path.join(input_dir, file_name)
            if os.path.isfile(file_path):
                # 检查文件是否为图片
                if file_name.lower().endswith(('.heic', '.jpeg', '.jpg')):
                    image_files.append(file_path)

        logging.info(f"找到{len(image_files)}张图片文件")

        # 处理所有图片
        processed_files = []
        for file_path in image_files:
            processed_path = self.process_image(file_path, output_dir)
            if processed_path:
                processed_files.append(processed_path)

        return processed_files

    def get_image_timestamp(self, image_path: str) -> str:
        """获取图片的拍摄时间"""
        try:
            image = Image.open(image_path)
            exif_data = image._getexif()
            if exif_data:
                timestamp = exif_data.get(36867)
                if timestamp:
                    timestamp = timestamp.strip()
                else:
                    timestamp = os.path.getmtime(image_path)
                    timestamp = time.strftime('%Y:%m:%d %H:%M:%S', time.localtime(timestamp))
                return timestamp
            else:
                # 如果没有EXIF数据，使用文件修改时间
                timestamp = os.path.getmtime(image_path)
                return time.strftime('%Y:%m:%d %H:%M:%S', time.localtime(timestamp))
        except Exception as e:
            logging.error(f"读取图片{image_path}时间戳失败: {e}")
            # 出错时使用文件修改时间
            timestamp = os.path.getmtime(image_path)
            return time.strftime('%Y:%m:%d %H:%M:%S', time.localtime(timestamp))

    def sort_images_by_timestamp(self, image_paths: list[str], reverse: bool = False) -> list[str]:
        """按照拍摄时间排序图片"""
        # 添加时间戳信息
        image_with_timestamp = []
        for image_path in image_paths:
            timestamp = self.get_image_timestamp(image_path)
            image_with_timestamp.append((image_path, timestamp))

        # 排序
        sorted_images = sorted(image_with_timestamp, key=lambda x: x[1], reverse=reverse)

        # 提取排序后的图片路径
        return [image_path for image_path, _ in sorted_images]


def main():
    """主函数，用于测试图像处理功能"""
    processor = ImageProcessor()

    # 测试目录处理
    input_dir = 'test_images'
    output_dir = 'processed_images'
    processed_files = processor.process_directory(input_dir, output_dir)

    # 测试排序
    sorted_files = processor.sort_images_by_timestamp(processed_files, reverse=False)
    logging.info(f"排序后的图片列表: {sorted_files}")


if __name__ == "__main__":
    main()