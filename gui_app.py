# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import filedialog, ttk, scrolledtext, messagebox
import os
import sys
import webbrowser
from markdown2 import markdown
import main_func
from image_processor import ImageProcessor
import logging
import threading
import time
from PIL import Image, ImageTk
import shutil
import json
# 导入LLM客户端注册中心
from llm_client import LLMClientRegistry

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ACPReportGenerator:
    def __init__(self, root):
        self.root = root
        self.root.title("ACP 总结报告工具")
        self.root.geometry("1000x700")
        self.root.minsize(800, 600)
        
        # 跟踪临时目录
        self.temp_dirs = []
        
        # 添加窗口关闭事件处理
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 设置中文字体
        self.style = ttk.Style()
        self.style.configure("TLabel", font=("SimHei", 10))
        self.style.configure("TButton", font=("SimHei", 10))
        self.style.configure("Header.TLabel", font=("SimHei", 14, "bold"))
        
        # 创建主框架
        self.main_frame = ttk.Frame(root, padding="20")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建左侧控制面板
        self.control_frame = ttk.LabelFrame(self.main_frame, text="控制面板", padding="10")
        self.control_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        
        # 选择文件夹按钮
        self.select_folder_btn = ttk.Button(
            self.control_frame, 
            text="选择图片文件夹", 
            command=self.select_folder
        )
        self.select_folder_btn.pack(fill=tk.X, pady=(0, 10))
        
        # 选择单个图片按钮
        self.select_file_btn = ttk.Button(
            self.control_frame, 
            text="选择单个图片", 
            command=self.select_file
        )
        self.select_file_btn.pack(fill=tk.X, pady=(0, 10))
        
        # 处理按钮
        self.process_btn = ttk.Button(
            self.control_frame, 
            text="生成总结报告", 
            command=self.start_processing,
            state=tk.DISABLED
        )
        self.process_btn.pack(fill=tk.X, pady=(0, 10))
        
        # 状态标签
        self.status_var = tk.StringVar()
        self.status_var.set("等待选择图片...")
        self.status_label = ttk.Label(
            self.control_frame, 
            textvariable=self.status_var, 
            relief=tk.SUNKEN, 
            anchor=tk.W
        )
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))
        
        # 创建进度条
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            self.control_frame,
            variable=self.progress_var,
            mode="determinate"
        )
        self.progress_bar.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))
        
        # 创建右侧报告显示区域
        self.report_frame = ttk.LabelFrame(self.main_frame, text="总结报告", padding="10")
        self.report_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # 创建标签页控件
        self.tab_control = ttk.Notebook(self.report_frame)
        
        # 创建原始报告标签页
        self.raw_report_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.raw_report_tab, text="Markdown 报告")
        
        # 创建渲染后的报告标签页
        self.rendered_report_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.rendered_report_tab, text="渲染报告")
        
        self.tab_control.pack(fill=tk.BOTH, expand=True)
        
        # 在原始报告标签页中添加文本框
        self.report_text = scrolledtext.ScrolledText(
            self.raw_report_tab, 
            wrap=tk.WORD,
            font=("SimHei", 10)
        )
        self.report_text.pack(fill=tk.BOTH, expand=True)
        
        # 在渲染报告标签页中添加占位标签
        self.html_label = ttk.Label(self.rendered_report_tab, text="报告将在这里渲染")
        self.html_label.pack(fill=tk.BOTH, expand=True)
        
        # 保存按钮
        self.save_btn = ttk.Button(
            self.control_frame, 
            text="保存报告", 
            command=self.save_report,
            state=tk.DISABLED
        )
        self.save_btn.pack(fill=tk.X, pady=(0, 10))
        
        # 打开浏览器按钮
        self.browser_btn = ttk.Button(
            self.control_frame, 
            text="在浏览器中查看", 
            command=self.open_in_browser,
            state=tk.DISABLED
        )
        self.browser_btn.pack(fill=tk.X, pady=(0, 10))

        # 配置按钮
        self.config_btn = ttk.Button(
            self.control_frame, 
            text="配置API密钥", 
            command=self.open_config_dialog
        )
        self.config_btn.pack(fill=tk.X, pady=(0, 10))
        
        # 初始化变量
        self.selected_paths = []
        self.report_content = ""
        self.html_content = ""
        # 加载配置
        self.load_config()
        
    def select_folder(self):
        """选择图片文件夹"""
        folder_path = filedialog.askdirectory(title="选择图片文件夹")
        if folder_path:
            self.selected_paths = [folder_path]
            self.status_var.set(f"已选择文件夹: {os.path.basename(folder_path)}")
            self.process_btn.config(state=tk.NORMAL)
    
    def select_file(self):
        """选择单个图片文件"""
        file_path = filedialog.askopenfilename(
            title="选择图片文件",
            filetypes=[
                ("图片文件", "*.jpeg *.jpg *.png *.heic"),
                ("所有文件", "*.*")
            ]
        )
        if file_path:
            self.selected_paths = [file_path]
            self.status_var.set(f"选择文件: {os.path.basename(file_path)}")
            self.process_btn.config(state=tk.NORMAL)
    
    def start_processing(self):
        """开始处理图片并生成报告"""
        if not self.selected_paths:
            self.status_var.set("请先选择图片文件夹或文件")
            return
        
        # 禁用按钮
        self.process_btn.config(state=tk.DISABLED)
        self.select_folder_btn.config(state=tk.DISABLED)
        self.select_file_btn.config(state=tk.DISABLED)
        self.status_var.set("正在处理图片...")
        self.progress_var.set(0)
        
        # 在新线程中处理
        threading.Thread(target=self.process_images).start()
    
    def process_images(self):
        """处理图片并生成报告"""
        try:
            # 禁用按钮
            self.process_btn.config(state=tk.DISABLED)
            self.select_folder_btn.config(state=tk.DISABLED)
            self.select_file_btn.config(state=tk.DISABLED)
            self.status_var.set("正在准备图片...")
            self.progress_var.set(0)

            # 创建临时目录
            import tempfile
            temp_dir = tempfile.mkdtemp(prefix="acp_temp_")
            # 跟踪临时目录
            self.temp_dirs.append(temp_dir)
            self.status_var.set(f"创建临时目录: {temp_dir}")

            # 检查路径类型并处理
            if os.path.isdir(self.selected_paths[0]):
                # 处理文件夹: 复制整个目录到临时目录
                folder_path = self.selected_paths[0]
                dest_path = os.path.join(temp_dir, os.path.basename(folder_path))
                shutil.copytree(folder_path, dest_path)
                self.status_var.set(f"已复制目录到临时位置: {dest_path}")
            else:
                # 处理单个文件: 创建目录并复制文件
                file_path = self.selected_paths[0]
                dest_dir = os.path.join(temp_dir, "single_file")
                os.makedirs(dest_dir, exist_ok=True)
                shutil.copy(file_path, dest_dir)
                self.status_var.set(f"已复制文件到临时位置: {dest_dir}")

            # 更新进度
            self.progress_var.set(20)

            # 使用图像处理器处理图片
            self.status_var.set("正在处理图片...")
            image_processor = ImageProcessor()

            # 处理所有非JPEG文件
            processed_files = []
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    # 处理图片
                    processed_file = image_processor.process_image(file_path, root)
                    if processed_file:
                        processed_files.append(processed_file)

            self.status_var.set(f"已处理 {len(processed_files)} 张图片")
            self.progress_var.set(50)

            # 按照文件创建时间从远到近排序图片
            self.status_var.set("正在排序图片...")
            # 定义按创建时间排序的函数
            def sort_by_creation_time(file_path):
                return os.path.getctime(file_path)
            
            # 排序图片
            sorted_images = sorted(processed_files, key=sort_by_creation_time)
            self.status_var.set(f"已排序 {len(sorted_images)} 张图片")
            self.progress_var.set(70)

            # 调用主函数处理
            self.status_var.set("正在生成总结报告...")
            main_func.main(images=sorted_images)

            # 读取生成的总结报告
            # 查找最新生成的final_summary_custom_*报告文件
            report_files = [f for f in os.listdir('.') if f.startswith('final_summary_custom_') and f.endswith('.md')]
            if report_files:
                report_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
                report_file = report_files[0]
                with open(report_file, 'r', encoding='utf-8') as f:
                    self.report_content = f.read()
                self.status_var.set(f"已读取报告文件: {report_file}")
            else:
                # 尝试查找其他可能的报告文件
                other_report_files = [f for f in os.listdir('.') if f.startswith('final_summary_') and f.endswith('.md')]
                if other_report_files:
                    other_report_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
                    report_file = other_report_files[0]
                    with open(report_file, 'r', encoding='utf-8') as f:
                        self.report_content = f.read()
                    self.status_var.set(f"已读取备用报告文件: {report_file}")
                else:
                    self.status_var.set("错误: 未找到生成的报告文件")
                    return

            # 更新UI
            self.root.after(0, self.update_report_display)
            
            # 更新状态
            self.status_var.set("报告生成完成")
            self.progress_var.set(100)
            
            # 启用按钮
            self.root.after(0, lambda: self.process_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.select_folder_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.select_file_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.save_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.browser_btn.config(state=tk.NORMAL))
            
        except Exception as e:
            logging.error(f"处理图片时出错: {str(e)}")
            self.status_var.set(f"处理出错: {str(e)}")
            self.root.after(0, lambda: self.process_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.select_folder_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.select_file_btn.config(state=tk.NORMAL))
        finally:
            # 清理当前临时目录
            if 'temp_dir' in locals() and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
                # 从跟踪列表中移除
                if temp_dir in self.temp_dirs:
                    self.temp_dirs.remove(temp_dir)
    
    def update_report_display(self):
        """更新报告显示"""
        # 更新Markdown文本框
        self.report_text.delete(1.0, tk.END)
        self.report_text.insert(tk.END, self.report_content)
        
        # 生成HTML内容
        self.html_content = markdown(self.report_content)
        
        # 保存HTML到临时文件
        temp_html = "temp_report.html"
        with open(temp_html, 'w', encoding='utf-8') as f:
            f.write(f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>ACP 总结报告</title>
                <style>
                    body {{ font-family: SimHei, Arial, sans-serif; margin: 20px; line-height: 1.6; }}
                    h1, h2, h3 {{ color: #333; }}
                    p {{ margin-bottom: 10px; }}
                    ul, ol {{ margin-bottom: 10px; margin-left: 20px; }}
                    code {{ background-color: #f5f5f5; padding: 2px 4px; border-radius: 4px; }}
                    pre {{ background-color: #f5f5f5; padding: 10px; border-radius: 4px; overflow-x: auto; }}
                </style>
            </head>
            <body>
                {self.html_content}
            </body>
            </html>
            """)
    
    def save_report(self):
        """保存报告"""
        if not self.report_content:
            self.status_var.set("没有可保存的报告内容")
            return
        
        save_path = filedialog.asksaveasfilename(
            defaultextension=".md",
            filetypes=[
                ("Markdown文件", "*.md"),
                ("文本文件", "*.txt"),
                ("所有文件", "*.*")
            ],
            title="保存报告"
        )
        if save_path:
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(self.report_content)
            self.status_var.set(f"报告已保存至: {save_path}")
    
    def open_in_browser(self):
        """在浏览器中打开报告"""
        if not self.html_content:
            self.status_var.set("没有可显示的报告内容")
            return
        
        # 创建临时HTML文件
        temp_html = "temp_report.html"
        webbrowser.open('file://' + os.path.realpath(temp_html))
        self.status_var.set("已在浏览器中打开报告")

    def open_config_dialog(self):
        """打开配置对话框"""
        ConfigDialog(self.root, self)

    def load_config(self):
        """加载配置"""
        config_file = "config.json"
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
            except Exception as e:
                logging.error(f"加载配置失败: {str(e)}")
                self.config = {}
        else:
            self.config = {}

    def save_config(self, config):
        """保存配置"""
        try:
            with open("config.json", 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            self.config = config
            return True
        except Exception as e:
            logging.error(f"保存配置失败: {str(e)}")
            return False

    def test_api_connection(self, api_type, api_key):
        """测试API连接"""
        try:
            # API类型到客户端类型的映射
            api_type_map = {
                "火山引擎": "ark",
                "DeepSeek": "silicon_flow"
            }
            
            # 检查API类型是否支持
            if api_type not in api_type_map:
                return False, f"不支持的API类型: {api_type}"
            
            # 获取客户端类型
            client_type = api_type_map[api_type]
            
            # 使用工厂类获取客户端实例
            client = LLMClientRegistry.get_client(client_type, api_key)
            
            # 使用客户端自带的测试方法
            success, message = client.test_connection()
            return success, message
        except Exception as e:
            return False, f"连接失败: {str(e)}"
    
    def on_closing(self):
        """窗口关闭事件处理"""
        # 清理所有临时目录
        for temp_dir in self.temp_dirs:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
        # 关闭窗口
        self.root.destroy()


class ConfigDialog(tk.Toplevel):
    """API配置对话框"""
    def __init__(self, parent, app):
        super().__init__(parent)
        self.parent = parent
        self.app = app
        self.title("API配置")
        self.geometry("400x300")
        self.resizable(False, False)
        
        # 使对话框模态
        self.grab_set()
        
        # 创建主框架
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # API类型选择
        ttk.Label(main_frame, text="API类型:", font=("SimHei", 10)).grid(row=0, column=0, sticky=tk.W, pady=(0, 10))
        self.api_type = tk.StringVar(value="火山引擎")
        api_type_frame = ttk.Frame(main_frame)
        api_type_frame.grid(row=0, column=1, sticky=tk.W, pady=(0, 10))
        
        ttk.Radiobutton(
            api_type_frame, 
            text="火山引擎", 
            variable=self.api_type, 
            value="火山引擎"
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Radiobutton(
            api_type_frame, 
            text="DeepSeek", 
            variable=self.api_type, 
            value="DeepSeek"
        ).pack(side=tk.LEFT)
        
        # API密钥输入
        ttk.Label(main_frame, text="API密钥:", font=("SimHei", 10)).grid(row=1, column=0, sticky=tk.W, pady=(0, 10))
        self.api_key_entry = ttk.Entry(main_frame, width=30, show="*")
        self.api_key_entry.grid(row=1, column=1, sticky=tk.W, pady=(0, 10))
        
        # 加载现有配置
        self.load_existing_config()
        
        # 校验按钮
        self.test_btn = ttk.Button(
            main_frame, 
            text="校验连接", 
            command=self.test_connection
        )
        self.test_btn.grid(row=2, column=0, columnspan=2, pady=(0, 10))
        
        # 状态标签
        self.status_var = tk.StringVar()
        self.status_var.set("请输入API密钥并校验连接")
        self.status_label = ttk.Label(
            main_frame, 
            textvariable=self.status_var, 
            anchor=tk.W
        )
        self.status_label.grid(row=3, column=0, columnspan=2, pady=(0, 10))
        
        # 按钮框架
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=(10, 0))
        
        # 保存按钮
        self.save_btn = ttk.Button(
            btn_frame, 
            text="保存配置", 
            command=self.save_dialog_config
        )
        self.save_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # 取消按钮
        self.cancel_btn = ttk.Button(
            btn_frame, 
            text="取消", 
            command=self.destroy
        )
        self.cancel_btn.pack(side=tk.LEFT)
        
    def load_existing_config(self):
        """加载现有配置"""
        api_type = self.app.config.get("api_type", "火山引擎")
        self.api_type.set(api_type)
        
        api_key = self.app.config.get("api_keys", {}).get(api_type, "")
        self.api_key_entry.insert(0, api_key)
        
    def test_connection(self):
        """测试API连接"""
        api_type = self.api_type.get()
        api_key = self.api_key_entry.get()
        
        if not api_key:
            messagebox.showerror("错误", "请输入API密钥")
            return
        
        self.status_var.set("正在测试连接...")
        self.update()
        
        # 在新线程中测试连接
        def test_thread():
            success, message = self.app.test_api_connection(api_type, api_key)
            self.app.root.after(0, lambda: self.update_test_result(success, message))
        
        threading.Thread(target=test_thread).start()
        
    def update_test_result(self, success, message):
        """更新测试结果"""
        if success:
            self.status_var.set(f"连接成功: {message}")
            messagebox.showinfo("成功", f"API连接测试成功: {message}")
        else:
            self.status_var.set(f"连接失败: {message}")
            messagebox.showerror("错误", f"API连接测试失败: {message}")
        
    def save_dialog_config(self):
        """保存配置"""
        api_type = self.api_type.get()
        api_key = self.api_key_entry.get()
        
        if not api_key:
            messagebox.showerror("错误", "请输入API密钥")
            return
        
        # 更新配置
        config = self.app.config.copy()
        config["api_type"] = api_type
        
        api_keys = config.get("api_keys", {})
        api_keys[api_type] = api_key
        config["api_keys"] = api_keys
        
        # 保存配置
        if self.app.save_config(config):
            messagebox.showinfo("成功", "配置已保存")
            self.destroy()
        else:
            messagebox.showerror("错误", "保存配置失败")


# 在ACPReportGenerator类中添加on_closing方法
# 找到类的最后一个方法并添加

# 假设test_api_connection是ACPReportGenerator类的最后一个方法
# 我们将在该方法后添加on_closing方法

# 查找并添加on_closing方法到正确的位置
# 首先找到test_api_connection方法的结束位置

# 添加on_closing方法
    def on_closing(self):
        """窗口关闭事件处理"""
        # 清理所有临时目录
        for temp_dir in self.temp_dirs:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
        # 关闭窗口
        self.root.destroy()

# 主函数保持不变
        # 处理按钮
        self.process_btn = ttk.Button(
            self.control_frame, 
            text="生成总结报告", 
            command=self.start_processing,
            state=tk.DISABLED
        )
        self.process_btn.pack(fill=tk.X, pady=(0, 10))
        
        # 状态标签
        self.status_var = tk.StringVar()
        self.status_var.set("等待选择图片...")
        self.status_label = ttk.Label(
            self.control_frame, 
            textvariable=self.status_var, 
            relief=tk.SUNKEN, 
            anchor=tk.W
        )
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))
        
        # 创建进度条
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            self.control_frame, 
            variable=self.progress_var,
            mode="determinate"
        )
        self.progress_bar.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))
        
        # 创建右侧报告显示区域
        self.report_frame = ttk.LabelFrame(self.main_frame, text="总结报告", padding="10")
        self.report_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # 创建标签页控件
        self.tab_control = ttk.Notebook(self.report_frame)
        
        # 创建原始报告标签页
        self.raw_report_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.raw_report_tab, text="Markdown 报告")
        
        # 创建渲染后的报告标签页
        self.rendered_report_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.rendered_report_tab, text="渲染报告")
        
        self.tab_control.pack(fill=tk.BOTH, expand=True)
        
        # 在原始报告标签页中添加文本框
        self.report_text = scrolledtext.ScrolledText(
            self.raw_report_tab, 
            wrap=tk.WORD,
            font=("SimHei", 10)
        )
        self.report_text.pack(fill=tk.BOTH, expand=True)
        
        # 在渲染报告标签页中添加占位标签
        self.html_label = ttk.Label(self.rendered_report_tab, text="报告将在这里渲染")
        self.html_label.pack(fill=tk.BOTH, expand=True)
        
        # 保存按钮
        self.save_btn = ttk.Button(
            self.control_frame, 
            text="保存报告", 
            command=self.save_report,
            state=tk.DISABLED
        )
        self.save_btn.pack(fill=tk.X, pady=(0, 10))
        
        # 打开浏览器按钮
        self.browser_btn = ttk.Button(
            self.control_frame, 
            text="在浏览器中查看", 
            command=self.open_in_browser,
            state=tk.DISABLED
        )
        self.browser_btn.pack(fill=tk.X, pady=(0, 10))

        # 配置按钮
        self.config_btn = ttk.Button(
            self.control_frame, 
            text="配置API密钥", 
            command=self.open_config_dialog
        )
        self.config_btn.pack(fill=tk.X, pady=(0, 10))
        
        # 初始化变量
        self.selected_paths = []
        self.report_content = ""
        self.html_content = ""
        # 加载配置
        self.load_config()
    
    def select_folder(self):
        """选择图片文件夹"""
        folder_path = filedialog.askdirectory(title="选择图片文件夹")
        if folder_path:
            self.selected_paths = [folder_path]
            self.status_var.set(f"已选择文件夹: {os.path.basename(folder_path)}")
            self.process_btn.config(state=tk.NORMAL)
    
    def select_file(self):
        """选择单个图片文件"""
        file_path = filedialog.askopenfilename(
            title="选择图片文件",
            filetypes=[
                ("图片文件", "*.jpeg *.jpg *.png *.heic"),
                ("所有文件", "*.*")
            ]
        )
        if file_path:
            self.selected_paths = [file_path]
            self.status_var.set(f"选择文件: {os.path.basename(file_path)}")
            self.process_btn.config(state=tk.NORMAL)
    
    def start_processing(self):
        """开始处理图片并生成报告"""
        if not self.selected_paths:
            self.status_var.set("请先选择图片文件夹或文件")
            return
        
        # 禁用按钮
        self.process_btn.config(state=tk.DISABLED)
        self.select_folder_btn.config(state=tk.DISABLED)
        self.select_file_btn.config(state=tk.DISABLED)
        self.status_var.set("正在处理图片...")
        self.progress_var.set(0)
        
        # 在新线程中处理
        threading.Thread(target=self.process_images).start()
    
    def process_images(self):
        """处理图片并生成报告"""
        try:
            # 禁用按钮
            self.process_btn.config(state=tk.DISABLED)
            self.select_folder_btn.config(state=tk.DISABLED)
            self.select_file_btn.config(state=tk.DISABLED)
            self.status_var.set("正在准备图片...")
            self.progress_var.set(0)

            # 创建临时目录
            import tempfile
            temp_dir = tempfile.mkdtemp(prefix="acp_temp_")
            # 跟踪临时目录
            self.temp_dirs.append(temp_dir)
            self.status_var.set(f"创建临时目录: {temp_dir}")

            # 检查路径类型并处理
            if os.path.isdir(self.selected_paths[0]):
                # 处理文件夹: 复制整个目录到临时目录
                folder_path = self.selected_paths[0]
                dest_path = os.path.join(temp_dir, os.path.basename(folder_path))
                shutil.copytree(folder_path, dest_path)
                self.status_var.set(f"已复制目录到临时位置: {dest_path}")
            else:
                # 处理单个文件: 创建目录并复制文件
                file_path = self.selected_paths[0]
                dest_dir = os.path.join(temp_dir, "single_file")
                os.makedirs(dest_dir, exist_ok=True)
                shutil.copy(file_path, dest_dir)
                self.status_var.set(f"已复制文件到临时位置: {dest_dir}")

            # 更新进度
            self.progress_var.set(20)

            # 使用图像处理器处理图片
            self.status_var.set("正在处理图片...")
            image_processor = ImageProcessor()

            # 处理所有非JPEG文件
            processed_files = []
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    # 处理图片
                    processed_file = image_processor.process_image(file_path, root)
                    if processed_file:
                        processed_files.append(processed_file)

            self.status_var.set(f"已处理 {len(processed_files)} 张图片")
            self.progress_var.set(50)

            # 按照文件创建时间从远到近排序图片
            self.status_var.set("正在排序图片...")
            # 定义按创建时间排序的函数
            def sort_by_creation_time(file_path):
                return os.path.getctime(file_path)
            
            # 排序图片
            sorted_images = sorted(processed_files, key=sort_by_creation_time)
            self.status_var.set(f"已排序 {len(sorted_images)} 张图片")
            self.progress_var.set(70)

            # 调用主函数处理
            self.status_var.set("正在生成总结报告...")
            main_func.main(images=sorted_images)

            # 读取生成的总结报告
            # 查找最新生成的final_summary_custom_*报告文件
            report_files = [f for f in os.listdir('.') if f.startswith('final_summary_custom_') and f.endswith('.md')]
            if report_files:
                report_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
                report_file = report_files[0]
                with open(report_file, 'r', encoding='utf-8') as f:
                    self.report_content = f.read()
                self.status_var.set(f"已读取报告文件: {report_file}")
            else:
                # 尝试查找其他可能的报告文件
                other_report_files = [f for f in os.listdir('.') if f.startswith('final_summary_') and f.endswith('.md')]
                if other_report_files:
                    other_report_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
                    report_file = other_report_files[0]
                    with open(report_file, 'r', encoding='utf-8') as f:
                        self.report_content = f.read()
                    self.status_var.set(f"已读取备用报告文件: {report_file}")
                else:
                    self.status_var.set("错误: 未找到生成的报告文件")
                    return

            # 更新UI
            self.root.after(0, self.update_report_display)
            
            # 更新状态
            self.status_var.set("报告生成完成")
            self.progress_var.set(100)
            
            # 启用按钮
            self.root.after(0, lambda: self.process_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.select_folder_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.select_file_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.save_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.browser_btn.config(state=tk.NORMAL))
            
        except Exception as e:
            logging.error(f"处理图片时出错: {str(e)}")
            self.status_var.set(f"处理出错: {str(e)}")
            self.root.after(0, lambda: self.process_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.select_folder_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.select_file_btn.config(state=tk.NORMAL))
        finally:
            # 清理当前临时目录
            if 'temp_dir' in locals() and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
                # 从跟踪列表中移除
                if temp_dir in self.temp_dirs:
                    self.temp_dirs.remove(temp_dir)
    
    def update_report_display(self):
        """更新报告显示"""
        # 更新Markdown文本框
        self.report_text.delete(1.0, tk.END)
        self.report_text.insert(tk.END, self.report_content)
        
        # 生成HTML内容
        self.html_content = markdown(self.report_content)
        
        # 保存HTML到临时文件
        temp_html = "temp_report.html"
        with open(temp_html, 'w', encoding='utf-8') as f:
            f.write(f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>ACP 总结报告</title>
                <style>
                    body {{ font-family: SimHei, Arial, sans-serif; margin: 20px; line-height: 1.6; }}
                    h1, h2, h3 {{ color: #333; }}
                    p {{ margin-bottom: 10px; }}
                    ul, ol {{ margin-bottom: 10px; margin-left: 20px; }}
                    code {{ background-color: #f5f5f5; padding: 2px 4px; border-radius: 4px; }}
                    pre {{ background-color: #f5f5f5; padding: 10px; border-radius: 4px; overflow-x: auto; }}
                </style>
            </head>
            <body>
                {self.html_content}
            </body>
            </html>
            """)
    
    def save_report(self):
        """保存报告"""
        if not self.report_content:
            self.status_var.set("没有可保存的报告内容")
            return
        
        save_path = filedialog.asksaveasfilename(
            defaultextension=".md",
            filetypes=[
                ("Markdown文件", "*.md"),
                ("文本文件", "*.txt"),
                ("所有文件", "*.*")
            ],
            title="保存报告"
        )
        if save_path:
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(self.report_content)
            self.status_var.set(f"报告已保存至: {save_path}")
    
    def open_in_browser(self):
        """在浏览器中打开报告"""
        if not self.html_content:
            self.status_var.set("没有可显示的报告内容")
            return
        
        # 创建临时HTML文件
        temp_html = "temp_report.html"
        webbrowser.open('file://' + os.path.realpath(temp_html))
        self.status_var.set("已在浏览器中打开报告")

    def open_config_dialog(self):
        """打开配置对话框"""
        ConfigDialog(self.root, self)

    def load_config(self):
        """加载配置"""
        config_file = "config.json"
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
            except Exception as e:
                logging.error(f"加载配置失败: {str(e)}")
                self.config = {}
        else:
            self.config = {}

    def save_config(self, config):
        """保存配置"""
        try:
            with open("config.json", 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            self.config = config
            return True
        except Exception as e:
            logging.error(f"保存配置失败: {str(e)}")
            return False

    def test_api_connection(self, api_type, api_key):
        """测试API连接"""
        try:
            # API类型到客户端类型的映射
            api_type_map = {
                "火山引擎": "ark",
                "DeepSeek": "silicon_flow"
            }
            
            # 检查API类型是否支持
            if api_type not in api_type_map:
                return False, f"不支持的API类型: {api_type}"
            
            # 获取客户端类型
            client_type = api_type_map[api_type]
            
            # 使用工厂类获取客户端实例
            client = LLMClientRegistry.get_client(client_type, api_key)
            
            # 使用客户端自带的测试方法
            success, message = client.test_connection()
            return success, message
        except Exception as e:
            return False, f"连接失败: {str(e)}"
    
    def on_closing(self):
        """窗口关闭事件处理"""
        # 清理所有临时目录
        for temp_dir in self.temp_dirs:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
        # 关闭窗口
        self.root.destroy()

# 恢复main函数定义
def main():
    """主函数"""
    root = tk.Tk()
    app = ACPReportGenerator(root)
    root.mainloop()

if __name__ == "__main__":
    main()