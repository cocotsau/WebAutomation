import base64
import io
import os
from typing import Optional, Union
from urllib.parse import urlparse

import requests
from PIL import Image
from requests.exceptions import RequestException


class ImgTools:
    """
    图片处理工具类（简洁通用版）
    核心：读取逻辑集中在两个读取方法，转换方法仅专注转换，无重复代码
    依赖：pip install pillow requests
    """

    # ------------------------------ 读取相关方法（集中处理读取逻辑）------------------------------
    @staticmethod
    def read_local_img(
        local_path: str,
        mode: str = "RGB"
    ) -> Optional[Image.Image]:
        """读取本地图片（仅处理本地路径，集中捕获读取异常）"""
        try:
            if not os.path.exists(local_path):
                print(f"错误：本地文件不存在 -> {local_path}")
                return None
            img = Image.open(local_path).convert(mode)
            print(f"本地图片读取成功：{local_path}（{img.size} | {img.mode}）")
            return img
        except (IOError, OSError) as e:
            print(f"错误：读取本地图片失败 -> {local_path} | {e}")
            return None
        except Exception as e:
            print(f"错误：本地图片读取未知异常 -> {local_path} | {e}")
            return None

    @staticmethod
    def read_url_img(
        img_url: str,
        mode: str = "RGB",
        timeout: int = 10
    ) -> Optional[Image.Image]:
        """读取网络图片（仅处理URL，集中捕获网络+读取异常）"""
        parsed = urlparse(img_url)
        if parsed.scheme not in ("http", "https"):
            print(f"错误：无效URL（需http/https开头）-> {img_url}")
            return None

        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            response = requests.get(img_url, stream=True, timeout=timeout, headers=headers, allow_redirects=True)
            response.raise_for_status()
            img = Image.open(io.BytesIO(response.content)).convert(mode)
            print(f"网络图片读取成功：{img_url}（{img.size} | {img.mode}）")
            return img
        except RequestException as e:
            print(f"错误：下载网络图片失败 -> {img_url} | {e}")
            return None
        except (IOError, OSError) as e:
            print(f"错误：解析网络图片失败 -> {img_url} | {e}")
            return None
        except Exception as e:
            print(f"错误：网络图片读取未知异常 -> {img_url} | {e}")
            return None

    @staticmethod
    def read_img(
        path_or_url: str,
        mode: str = "RGB",
        timeout: int = 10
    ) -> Optional[Image.Image]:
        """统一读取入口（自动识别本地路径/URL，内部转发到对应读取方法）"""
        parsed = urlparse(path_or_url)
        if parsed.scheme in ("http", "https"):
            return ImgTools.read_url_img(path_or_url, mode, timeout)
        else:
            return ImgTools.read_local_img(path_or_url, mode)

    # ------------------------------ 转换相关方法（仅专注转换，复用读取逻辑）------------------------------
    @staticmethod
    def webp_to_png(
        input_source: Union[str, Image.Image],
        output_path: str,
        preserve_alpha: bool = True
    ) -> bool:
        """
        WebP 转 PNG（无重复读取逻辑，内部复用 read_img）
        :param input_source: 输入源（本地路径/网络URL字符串 | PIL Image 对象）
        :param output_path: 输出PNG路径（含.png后缀）
        :param preserve_alpha: 是否保留透明通道
        :return: 转换成功True，失败False
        """
        try:
            # 第一步：统一获取有效 Image 对象（复用已有的读取逻辑）
            img = None
            if isinstance(input_source, str):
                # 输入是字符串（路径/URL）：调用统一读取方法
                img = ImgTools.read_img(input_source)
                if not img:
                    print("错误：输入字符串对应的图片读取失败，无法转换")
                    return False
                # 验证是否为 WebP 格式（仅对字符串输入验证，因为Image对象可能是用户预处理后的）
                if img.format != "WEBP":
                    print(f"错误：输入文件不是 WebP 格式（实际格式：{img.format}）")
                    return False
            elif isinstance(input_source, Image.Image):
                # 输入是 Image 对象：直接使用（信任用户传入的有效性）
                img = input_source
            else:
                print(f"错误：不支持的输入类型 -> {type(input_source)}（仅支持字符串/Image对象）")
                return False

            # 第二步：核心转换逻辑（仅做转换，无读取代码）
            mode = "RGBA" if preserve_alpha and img.mode in ("RGBA", "LA") else "RGB"
            img.convert(mode).save(output_path, format="PNG", optimize=True)
            print(f"✅ WebP 转 PNG 成功：{output_path}（模式：{mode}）")
            return True

        except (IOError, OSError) as e:
            print(f"错误：保存 PNG 失败 -> {output_path} | {e}")
            return False
        except Exception as e:
            print(f"错误：WebP 转 PNG 未知异常 -> {e}")
            return False

    @staticmethod
    def base64_to_png(
        base64_str: str,
        preserve_alpha: bool = True
    ) -> Optional[Image.Image]:
        """
        将 Base64 编码字符串转换为 PNG 格式的 Image 对象
        :param base64_str: Base64 编码字符串（支持带 data URI 前缀或纯编码）
        :param preserve_alpha: 是否保留透明通道（默认 True）
        :return: 转换成功返回 PIL Image 对象，失败返回 None
        """
        try:
            # 解码（核心逻辑）
            if "base64," in base64_str:
                base64_str = base64_str.split("base64,")[-1]
            img_bytes = base64.b64decode(base64_str, validate=True)

            # 读取（复用 Image.open，无重复异常处理）
            with io.BytesIO(img_bytes) as buf:
                img = Image.open(buf)

                # 转换模式（保留透明通道逻辑）
                mode = "RGBA" if preserve_alpha and img.mode in ("RGBA", "LA") else "RGB"
                converted_img = img.convert(mode)
            # print(f"✅ Base64 转 Image 对象成功（模式：{mode} | 尺寸：{converted_img.size}）")
            return converted_img

        except base64.binascii.Error as e:
            print(f"错误：Base64 编码无效 -> {e}")
            return None
        except (IOError, OSError) as e:
            print(f"错误：Base64 解码后不是有效图片 -> {e}")
            return None
        except Exception as e:
            print(f"错误：Base64 转 Image 对象未知异常 -> {e}")
            return None

    @staticmethod
    def save_img(
        img: Image.Image,
        output_path: str,
        format: str = "PNG",
        optimize: bool = True
    ) -> bool:
        """
        保存 Image 对象到本地文件
        :param img: 要保存的 PIL Image 对象
        :param output_path: 输出文件路径（含文件后缀，如 .png、.jpg）
        :param format: 保存格式（默认 PNG，支持 JPEG、GIF 等 PIL 支持的格式）
        :param optimize: 是否优化图片（默认 True，仅对 PNG/JPEG 有效）
        :return: 保存成功返回 True，失败返回 False
        """
        try:
            if not isinstance(img, Image.Image):
                print(f"错误：不支持的输入类型 -> {type(img)}（仅支持 PIL Image 对象）")
                return False
            
            # 确保输出目录存在
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
            
            img.save(output_path, format=format, optimize=optimize)
            print(f"✅ 图片保存成功：{output_path}（格式：{format}）")
            return True
        except (IOError, OSError) as e:
            print(f"错误：保存图片失败 -> {output_path} | {e}")
            return False
        except Exception as e:
            print(f"错误：图片保存未知异常 -> {e}")
            return False


# ------------------------------ 简洁使用示例 ------------------------------
if __name__ == "__main__":
    tool = ImgTools()

    # 1. 输入：本地WebP路径（内部复用 read_local_img）
    tool.webp_to_png("input.webp", "output_local.png", preserve_alpha=True)

    # 2. 输入：网络WebP URL（内部复用 read_url_img）
    tool.webp_to_png("https://picsum.photos/400/200.webp", "output_url.png", preserve_alpha=False)

    # 3. 输入：已读取的 Image 对象（直接使用，不重复读取）
    img = tool.read_img("test.webp")
    if img:
        tool.webp_to_png(img, "output_img_obj.png")

    # 4. Base64 转 Image 对象 + 保存（新使用方式）
    sample_base64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    # 转换为 Image 对象
    base64_img = tool.base64_to_png(sample_base64, preserve_alpha=True)
    if base64_img:
        # 使用 save_img 保存
        tool.save_img(base64_img, "output_base64.png")
        
        # 也可以保存为其他格式（如 JPEG）
        tool.save_img(base64_img.convert("RGB"), "output_base64.jpg", format="JPEG")