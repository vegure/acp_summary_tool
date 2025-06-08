# -*- coding: utf-8 -*-
import time
import sys
import os
import logging
import re

from openai import OpenAI
from PIL import Image
from fastmcp import Client
import tqdm
import pillow_heif

from silicon_flow_client import get_silicon_flow_response

pillow_heif.register_heif_opener()

# 设置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
LLM_MODEL_NAME = 'bot-20250607114747-jcqlf' # 'deepseek-r1-250528' # 'deepseek-r1-250120'
VLM_MODEL_NAME = 'doubao-vision-pro-32k-241028'

import base64
from multiprocessing import Pool, cpu_count


def read_heic(image_path):
    """读取HEIC格式的图片"""
    try:
        image = Image.open(image_path)
        return image
    except ImportError:
        logging.error("PIL库未安装，请安装Pillow库以支持HEIC格式图片处理。")
        sys.exit(1)
    except Exception as e:
        logging.error(f"读取HEIC图片失败: {e}")
        return None


def reformate_heic_to_jpeg(image_dir):
    # 将制定image_dir目录下的HEIC图片转换为JPEG格式
    heic_files = [f for f in os.listdir(image_dir) if f.lower().endswith('.heic')]
    if not heic_files:
        logging.info("没有找到HEIC格式的图片文件。")
        return
    logging.info(f"找到{len(heic_files)}张HEIC格式的图片文件，开始转换为JPEG格式。")
    for heic_file in heic_files:
        heic_path = os.path.join(image_dir, heic_file)
        image = read_heic(heic_path)
        if image:
            jpeg_path = os.path.splitext(heic_path)[0] + '.jpeg'
            # 保留照片的exif_data
            exif_data = image.info.get('exif', None)
            if exif_data:
                image.save(jpeg_path, 'JPEG', exif=exif_data)
            else:
                image.save(jpeg_path, 'JPEG')
            logging.info(f"已将{heic_file}转换为JPEG格式，保存为{jpeg_path}")
        else:
            logging.error(f"无法读取或转换图片: {heic_file}")


def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


def get_image_timestamp(image_path):
    """获取图片的拍摄时间
    """
    try:
        image = Image.open(image_path)
        exif_data = image._getexif()
        if exif_data:
            timestamp = exif_data.get(36867)
            if timestamp:
                timestamp = timestamp.strip()
            else:
                timestamp = os.path.getmtime(image_path)
                # 转换成字符串表示的时间 按照YYYY:MM:DD HH:mm:SS格式
                timestamp = time.strftime('%Y:%m:%d %H:%M:%S', time.localtime(timestamp))
            return timestamp
        else:
            return None
    except Exception as e:
        logging.error(f"Error reading image {image_path}: {e}")
        return None


class LLMClient:
    """LLM客户端，负责与大语言模型API通信"""

    def __init__(self, models: dict, url: str, api_key: str) -> None:
        self.models = models
        self.url: str = url
        self.client = OpenAI(api_key=api_key, base_url=url)

    def get_response(self, messages: list[dict[str, str]], task='llm') -> str:
        """发送消息给LLM并获取响应"""
        response = self.client.chat.completions.create(
            model=self.models[task],
            messages=messages,
            stream=False,
            timeout=1000,  # 设置超时时间为1000秒
        )
        return response.choices[0].message.content

class ArkClient(LLMClient):
    base_url = 'https://ark.cn-beijing.volces.com/api/v3'
    api_key = '66bc3c5e-3ac0-4a2e-a15d-dc3fdcf90b30'
    models = {
        'llm': 'doubao-1-5-thinking-pro-250415',
        'vlm': 'doubao-vision-pro-32k-241028',
    }
    """Ark客户端，继承自LLMClient，专门用于处理Ark平台的请求"""
    def __init__(self) -> None:
        super().__init__(self.models, self.base_url, self.api_key)


class SiliconFlowClient(LLMClient):
    """SiliconFlow客户端，继承自LLMClient，专门用于处理SiliconFlow平台的请求"""
    base_url = 'https://api.siliconflow.cn/v1'
    api_key = 'sk-tjunxlkierjzjmfdzcrztynylbtmnpxgcluthvxjnhzxggwc'
    models = {
        'llm': 'Pro/deepseek-ai/DeepSeek-R1',
        'vlm': 'Qwen/Qwen2.5-VL-32B-Instruct',
    }
    def __init__(self) -> None:
        super().__init__(self.models, self.base_url, self.api_key)


def main(service='silicon_flow', postfixes=''):
    llm_client = SiliconFlowClient() if service == 'silicon_flow' else ArkClient()
    # 遍历macos下照片文件
    images = []
    if isinstance(postfixes, str):
        postfixes = [postfixes]
    elif isinstance(postfixes, list):
        postfixes = postfixes
    else:
        raise TypeError("postfix参数必须是字符串或字符串列表")

    for postfix in postfixes:
        photo_dir = 'images' + '_' + postfix
        photo_files = [f for f in os.listdir(photo_dir) if f.endswith('.jpeg')]
        logging.info(f"在{photo_dir}找到{len(photo_files)}张照片文件")
        for photo_file in photo_files:
            photo_path = os.path.join(photo_dir, photo_file)
            images.append(photo_path)

    # 按照get_image_timestamp函数对图片进行排序
    sorted_images = sorted(
        images, key=lambda x: get_image_timestamp(x), reverse=False
    )
    # 从拍摄的slides中提取图片内容信息
    images_desc_file = f'images_desc_{'_'.join(postfixes)}.md'
    if not os.path.exists(images_desc_file):
        idx = 1
        for image in tqdm.tqdm(sorted_images):
            message = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{encode_image(image)}",
                            },
                        },
                        {"type": "text", "text": "你是一个专业学者，从当前输入的图片中找到slide内容，并且提取其中的信息。"},
                    ],
                }
            ]
            response = llm_client.get_response(messages=message, task='vlm')
            print(response)
            with open(images_desc_file, 'a') as f:
                f.write(f'第{idx}张图片\n' + response.split('</think>')[-1] + '\n')
            idx += 1
    # 读取images_desc文件内容，并进行总结
    with open(images_desc_file, 'r', encoding='utf-8') as f:
        images_desc = f.read()
    # 如果images_desc内容过长，可以分段处理，单个段落不超过102400个字符，分段时必须以“第x张图片”作为分隔符
    # 首先基于正则表达式，按照"第x张图片"作为分隔符，将images_desc进行分段
    segments = re.split(r'第\d+张图片\s*\n', images_desc)
    logging.info(f"分割后的段落数量: {len(segments)}")
    # 去除空段落
    segments = [segment.strip() for segment in segments if segment.strip()]
    logging.info(f"去除空段落后的段落数量: {len(segments)}")
    # 对分割后的段落进行合并，每个段落不超过max_length个字符
    max_length = 50 * 1024  # 50k字符
    merged_segments = []
    current_segment = ""
    for segment in segments:
        if len(current_segment) + len(segment) + 1 <= max_length:
            if current_segment:
                current_segment += "\n"  # 添加换行符
            current_segment += segment
        else:
            merged_segments.append(current_segment)
            current_segment = segment
    # 对提取的slides信息进行总结
    segments_desc = []
    for idx, segment in tqdm.tqdm(enumerate(merged_segments), desc="处理分段总结"):
        prompt = f"""
        你是一个学术会议参会报告总结专家，请根据以下图片内容，分专题进行总结，并输出一个总结报告。
        总结时需要注意：
        1. 每个专题可能关联多张图片，需对每个专题的内容进行精准归纳与提炼。
        2. 总结内容应做到逻辑清晰、言简意赅，着重突出关键要点。
        【原始内容】
        第{idx + 1}段内容：
        {segment}
        """
        message = [{"role": "user", "content": prompt}]
        response = llm_client.get_response(messages=message)
        segments_desc.append(f"第{idx + 1}段总结：\n{response.split('</think>')[-1]}")
    # 对多段总结描述进行最终总结
    segments_desc_combined = "\n".join(segments_desc)
    prompt = f"""
    【任务描述】
        你作为一名专业的学术会议参会报告总结专家，需依据以下分段总结内容进行归纳，生成一份条理清晰、重点突出的简要会议总结。
    【总结要求】
        1. 总结内容需具备高度的逻辑性和专业性，精准提炼关键要点，避免冗余表述。
        2. 确保内容简洁明了，杜绝重复信息和多余语句。
    【原始分段总结内容】
        {segments_desc_combined}
    """
    message = [{"role": "user", "content": prompt}]
    response = llm_client.get_response(messages=message)
    print(f"最终总结：{response.split('</think>')[-1]}")
    with open(f'final_summary_{'_'.join(postfixes)}.md', 'w') as f:
        f.write(response.split('</think>')[-1])


if __name__ == "__main__":
    # reformate_heic_to_jpeg('images_0608')
    main(postfixes=['0607', '0608'])
    # # 测试LLM任务
    # llm_response = SiliconFlowClient().get_response(
    #     messages=[{"role": "user", "content": "介绍下你自己!"}],
    #     task='llm'
    # )
    # print("LLM Response:\n", llm_response)

    # # 测试VLM任务
    # vlm_response = SiliconFlowClient().get_response(
    #     messages=[{
    #                 "role": "user",
    #                 "content": [
    #                     {
    #                         "type": "image_url",
    #                         "image_url": {
    #                             "url": f"data:image/jpeg;base64,{encode_image('images/102E4A16-75FE-4BBD-A37B-90FCAAD00448.jpeg')}",
    #                         },
    #                     },
    #                     {"type": "text", "text": "你是一个专业学者，从当前输入的图片中找到slide内容，并且提取其中的信息。"},
    #                 ],
    #             }],
    #     task='vlm'
    # )
    # print("VLM Response:\n", vlm_response)
