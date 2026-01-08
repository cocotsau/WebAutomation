from io import BytesIO
from PIL import Image

try:
    import ddddocr
except ImportError:
    ddddocr = None


class ImgOcr:
    """
    验证码识别器（基于ddddocr）
    支持多种图片格式的PIL Image对象，输出识别结果字符串
    """

    def __init__(self, show_ad: bool = False):
        """
        初始化识别器
        
        :param show_ad: 是否显示广告（ddddocr参数）
        """
        if ddddocr is None:
            raise RuntimeError("OCR library 'ddddocr' (or its dependency 'onnxruntime') is not installed or failed to load. Please check your installation.")
            
        self.ocr = ddddocr.DdddOcr(show_ad=show_ad)

    def recognize(self, img: Image.Image) -> str:
        """
        识别验证码（支持多种图片格式）
        
        :param img: 任意格式的有效PIL Image对象（如PNG、JPG、GIF等）
        :return: 识别结果文本
        :raises ValueError: 图片对象无效
        :raises RuntimeError: 识别过程中发生错误
        """
        try:
            # 验证图片有效性
            self._validate_image(img)
            
            # 处理图片并执行识别
            img_bytes = self._process_image(img)
            return self.ocr.classification(img_bytes)
            
        except ValueError as ve:
            raise ve
        except Exception as e:
            raise RuntimeError(f"验证码识别失败: {str(e)}")

    def _validate_image(self, img: Image.Image) -> None:
        """
        验证图片对象是否有效
        
        :param img: PIL Image对象
        :raises ValueError: 图片对象无效
        """
        try:
            # 验证图片完整性（会检查文件结构是否合法）
            img.verify()
        except Exception:
            raise ValueError("无效的图片对象")

    def _process_image(self, img: Image.Image) -> bytes:
        """
        处理图片：转换为RGB模式并统一转为PNG字节数据（适配ddddocr）
        
        :param img: 原始图片对象（支持多种格式）
        :return: 处理后的PNG字节数据
        """
        # 转换为RGB模式（解决透明通道、灰度图等格式兼容性问题）
        if img.mode != "RGB":
            img = img.convert("RGB")
        
        # 统一保存为PNG字节数据（ddddocr对PNG格式兼容性更好）
        img_buffer = BytesIO()
        img.save(img_buffer, format="PNG")
        return img_buffer.getvalue()


# 使用示例
if __name__ == "__main__":
    try:
        # 示例1：从文件加载图片（支持PNG、JPG、BMP等格式）
        with Image.open("captcha.jpg") as img:  # 这里可以是任意有效图片格式
            recognizer = ImgOcr(show_ad=False)
            result = recognizer.recognize(img)
            print(f"识别结果: {result}")
            
        # 示例2：从网络获取图片（示例）
        # import requests
        # response = requests.get("https://example.com/captcha.png")
        # response.raise_for_status()
        # with Image.open(BytesIO(response.content)) as img:
        #     recognizer = ImgOcr(show_ad=False)
        #     result = recognizer.recognize(img)
        #     print(f"网络图片识别结果: {result}")
            
    except ValueError as ve:
        print(f"输入错误: {ve}")
    except RuntimeError as re:
        print(f"识别错误: {re}")
    except Exception as e:
        print(f"未知错误: {e}")