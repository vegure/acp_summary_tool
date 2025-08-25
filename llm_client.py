import os
import json
import logging
from abc import ABC, abstractmethod
from openai import OpenAI

# 设置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 加载配置
def load_config():
    """加载配置文件"""
    config_file = "config.json"
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"加载配置失败: {str(e)}")
            return {}
    else:
        return {}

# 客户端注册中心
class LLMClientRegistry:
    """LLM客户端注册中心，用于管理和获取不同类型的LLM客户端"""
    _clients = {}

    @classmethod
    def register_client(cls, client_type: str, client_class):
        """注册客户端类"""
        cls._clients[client_type] = client_class

    @classmethod
    def get_client(cls, client_type: str, api_key=None, config=None):
        """根据类型获取客户端实例
        
        Args:
            client_type: 客户端类型
            api_key: API密钥
            config: 额外配置参数，特别是针对本地大模型的配置
        
        Returns:
            LLMClient实例
        """
        if client_type not in cls._clients:
            raise ValueError(f"不支持的客户端类型: {client_type}")
            
        # 对于本地大模型客户端，需要传递额外的配置参数
        if client_type == 'local_llm' and config:
            return cls._clients[client_type](api_key, config)
        
        # 对于其他客户端，只传递api_key
        return cls._clients[client_type](api_key)

    @classmethod
    def get_supported_types(cls):
        """获取所有支持的客户端类型"""
        return list(cls._clients.keys())

class LLMClient(ABC):
    """LLM客户端抽象基类，定义与大语言模型API通信的接口"""

    def __init__(self, models: dict, url: str, api_key: str) -> None:
        self.models = models
        self.url: str = url
        self.client = OpenAI(api_key=api_key, base_url=url)

    def get_response(self, messages: list[dict[str, str]], task='llm', max_retry=3) -> str:
        """发送消息给LLM并获取响应"""
        for _ in range(max_retry):
            try:
                response = self.client.chat.completions.create(
                    model=self.models[task],
                    messages=messages,
                    stream=False,
                    timeout=1000,  # 设置超时时间为1000秒
                )
                return response.choices[0].message.content
            except Exception as e:
                logging.error(f"Failed to get response from LLM: {str(e)}")
                continue
        raise RuntimeError("Failed to get response from LLM.")

    @abstractmethod
    def test_connection(self) -> tuple[bool, str]:
        """测试API连接
        返回: (是否成功, 消息)
        """
        pass

class ArkClient(LLMClient):
    base_url = 'https://ark.cn-beijing.volces.com/api/v3'
    models = {
        'llm': 'doubao-1-5-thinking-pro-250415',
        'vlm': 'doubao-vision-pro-32k-241028',
    }
    """Ark客户端，继承自LLMClient，专门用于处理火山引擎平台的请求"""
    def __init__(self, api_key=None) -> None:
        # 如果没有提供api_key，则从配置文件中加载
        if api_key is None:
            config = load_config()
            api_key = config.get('api_keys', {}).get('火山引擎', '')
        super().__init__(self.models, self.base_url, api_key)

    def test_connection(self) -> tuple[bool, str]:
        """测试火山引擎API连接"""
        try:
            # 发送测试请求
            response = self.get_response(
                messages=[{"role": "user", "content": "测试连接"}],
                task='llm'
            )
            return True, "连接成功"
        except Exception as e:
            return False, f"连接失败: {str(e)}"


class SiliconFlowClient(LLMClient):
    """SiliconFlow客户端，继承自LLMClient，专门用于处理DeepSeek平台的请求"""
    base_url = 'https://api.siliconflow.cn/v1'
    models = {
        'llm': 'Pro/deepseek-ai/DeepSeek-R1',
        'vlm': 'Qwen/Qwen2.5-VL-32B-Instruct',
    }
    def __init__(self, api_key=None) -> None:
        # 如果没有提供api_key，则从配置文件中加载
        if api_key is None:
            config = load_config()
            api_key = config.get('api_keys', {}).get('DeepSeek', '')
        super().__init__(self.models, self.base_url, api_key)

    def test_connection(self) -> tuple[bool, str]:
        """测试DeepSeek API连接"""
        try:
            # 发送测试请求
            response = self.get_response(
                messages=[{"role": "user", "content": "测试连接"}],
                task='llm'
            )
            return True, "连接成功"
        except Exception as e:
            return False, f"连接失败: {str(e)}"


class LocalLLMClient(LLMClient):
    """本地大模型客户端，继承自LLMClient，用于处理本地部署的大模型服务"""
    def __init__(self, api_key=None, config=None) -> None:
        # 如果没有提供参数，则从配置文件中加载
        default_config = load_config()
        if api_key is None:
            api_key = default_config.get('api_keys', {}).get('本地大模型', '')
        
        # 合并默认配置和传入的配置
        local_llm_config = {**default_config.get('local_llm', {}), **(config or {})}
        
        # 为LLM和VLM任务分别获取配置
        llm_address = local_llm_config.get('llm_address', local_llm_config.get('address', 'localhost'))
        llm_port = local_llm_config.get('llm_port', local_llm_config.get('port', '8000'))
        llm_model_name = local_llm_config.get('llm_model_name', local_llm_config.get('model_name', 'gpt-4o'))
        
        vlm_address = local_llm_config.get('vlm_address', llm_address)
        vlm_port = local_llm_config.get('vlm_port', llm_port)
        vlm_model_name = local_llm_config.get('vlm_model_name', llm_model_name)
        
        # 构建base_url，对于不同任务可能有不同的地址和端口
        llm_base_url = f'http://{llm_address}:{llm_port}/v1'
        vlm_base_url = f'http://{vlm_address}:{vlm_port}/v1'
        
        # 定义模型配置
        models = {
            'llm': llm_model_name,
            'vlm': vlm_model_name,
        }
        
        # 存储基础URL，用于后续可能的扩展
        self.base_urls = {
            'llm': llm_base_url,
            'vlm': vlm_base_url,
        }
        
        # 对于基类，我们使用LLM的基础URL
        super().__init__(models, llm_base_url, api_key)

    def get_response(self, messages: list[dict[str, str]], task='llm', max_retry=3) -> str:
        """发送消息给LLM并获取响应"""
        # 根据任务类型选择不同的基础URL
        base_url = self.base_urls.get(task, self.url)
        
        # 创建对应的客户端
        client = OpenAI(api_key=self.client.api_key, base_url=base_url)
        
        for _ in range(max_retry):
            try:
                response = client.chat.completions.create(
                    model=self.models[task],
                    messages=messages,
                    stream=False,
                    timeout=1000,  # 设置超时时间为1000秒
                )
                return response.choices[0].message.content
            except Exception as e:
                logging.error(f"Failed to get response from {task} model: {str(e)}")
                continue
        raise RuntimeError(f"Failed to get response from {task} model.")

    def test_connection(self) -> tuple[bool, str]:
        """测试本地大模型API连接"""
        try:
            # 发送测试请求
            response = self.get_response(
                messages=[{"role": "user", "content": "测试连接"}],
                task='llm'
            )
            return True, "连接成功"
        except Exception as e:
            return False, f"连接失败: {str(e)}"


# 注册客户端
LLMClientRegistry.register_client('ark', ArkClient)
LLMClientRegistry.register_client('silicon_flow', SiliconFlowClient)
LLMClientRegistry.register_client('local_llm', LocalLLMClient)