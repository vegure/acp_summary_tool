# -*- coding: utf-8 -*-
import time
import sys
import os
import logging
import re
import base64
import concurrent.futures
from multiprocessing import Pool, cpu_count

from PIL import Image
from fastmcp import Client
import tqdm

# 导入新的图像处理模块
from image_processor import ImageProcessor
# 导入LLM客户端相关类
from llm_client import LLMClientRegistry, load_config
import threading

# 设置日志记录
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


def main(service=None, images=None):
    # 如果没有指定service，则从配置文件中加载
    if service is None:
        config = load_config()
        api_type = config.get('api_type', '火山引擎')
        if api_type == 'DeepSeek':
            service = 'silicon_flow'
        elif api_type == '本地大模型':
            service = 'local_llm'
        else:
            service = 'ark'
    
    # 通过注册中心获取客户端实例
    if service == 'local_llm':
        # 对于本地大模型，获取配置
        config = load_config()
        local_llm_config = config.get('local_llm', {})
        # 获取API密钥
        api_key = config.get('api_keys', {}).get('本地大模型', '')
        # 直接传递local_llm_config作为配置参数
        llm_client = LLMClientRegistry.get_client(service, api_key, local_llm_config)
    else:
        llm_client = LLMClientRegistry.get_client(service)
    # 创建图像处理器实例
    image_processor = ImageProcessor()

    # 如果没有提供图片列表，则使用默认逻辑
    if images is None:
        # 遍历macos下照片文件
        images = []
        postfixes = 'default'
        if isinstance(postfixes, str):
            postfixes = [postfixes]
        elif isinstance(postfixes, list):
            postfixes = postfixes
        else:
            raise TypeError("postfix参数必须是字符串或字符串列表")

        for postfix in postfixes:
            photo_dir = 'images' + '_' + postfix
            # 使用图像处理器处理目录下的所有图片
            processed_files = image_processor.process_directory(photo_dir)
            logging.info(f"在{photo_dir}处理了{len(processed_files)}张照片文件")
            images.extend(processed_files)

        # 使用图像处理器按照拍摄时间排序图片（从远到近）
        sorted_images = image_processor.sort_images_by_timestamp(images, reverse=False)
    else:
        # 使用提供的图片列表
        sorted_images = images
    # 从拍摄的slides中提取图片内容信息
    # 确定报告文件名
    if images is not None:
        # 如果传入了图片列表，使用时间戳作为唯一标识
        timestamp = int(time.time())
        images_desc_file = f"images_desc_custom_{timestamp}.md"
        final_summary_file = f"final_summary_custom_{timestamp}.md"
    else:
        # 使用原来的逻辑
        images_desc_file = f"images_desc_{'_'.join(postfixes)}.md"
        final_summary_file = f"final_summary_{'_'.join(postfixes)}.md"

    if not os.path.exists(images_desc_file):
        idx = 1
    # 定义一个函数用于处理单张图片并返回结果
    def process_image(image, idx, llm_client):
        """
        处理单张图片并返回结果
        
        :param image: 图片文件路径
        :param idx: 图片索引
        :param llm_client: LLM客户端实例
        :return: (索引, 处理结果)元组
        """
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
        return (idx, response.split('wyaf')[-1])

    # 使用线程池处理图片，并保持结果顺序
    max_threads = 8
    results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_threads) as executor:
        # 提交所有任务
        future_to_idx = {
            executor.submit(process_image, sorted_images[idx], idx + 1, llm_client): idx
            for idx in range(len(sorted_images))
        }

        # 收集结果，确保按顺序处理
        for future in tqdm.tqdm(concurrent.futures.as_completed(future_to_idx), desc="Processing images", total=len(sorted_images)):
            idx, result = future.result()
            results.append((idx, result))

    # 按索引顺序排序结果
    results.sort(key=lambda x: x[0])

    # 按顺序写入文件
    with open(images_desc_file, 'w') as f:
        for idx, result in results:
            f.write(f'第{idx}张图片\n{result}\n')
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
    max_length = 10 * 1024  # 50k字符
    merged_segments = []
    current_segment = ""
    for segment in tqdm.tqdm(segments, desc="合并段落"):
        if len(current_segment) + len(segment) + 1 <= max_length:
            if current_segment:
                current_segment += "\n"  # 添加换行符
            current_segment += segment
        else:
            merged_segments.append(current_segment)
            current_segment = segment
    merged_segments.append(current_segment)
    logging.info(f"分段数：{len(merged_segments)}")
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
    logging.info(f"进行语义分割后的主题数量为：{len(segments_desc)}")
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
    with open(final_summary_file, "w") as f:
        f.write(response.split("[SPEAK]")[-1])


if __name__ == "__main__":
    # reformate_heic_to_jpeg('images_0608')
    main(postfixes=["0607", "0608"])
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
