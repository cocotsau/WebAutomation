from typing import Union, List, Tuple, Optional
import requests
import json
import time  # 用于重试间隔
from datetime import datetime


class Notification:
    """通知基类，定义通知接口"""
    
    def send(self, message):
        """发送通知的抽象方法，子类需实现"""
        raise NotImplementedError("子类必须实现send方法")


class WeChatNotification(Notification):
    """企业微信机器人通知类，支持超时设置、重试机制，通过机器人key发送通知"""
    
    # 企业微信机器人webhook固定前缀（key拼接在后面）
    _WEBHOOK_PREFIX = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key="

    # 企微支持的颜色列表（仅保留有效类型）
    _SUPPORTED_COLORS = {"comment", "warning", "info", "normal"}
    
    def __init__(
        self, 
        wechat_keys: Union[str, List[str]],  # 企微机器人key（单个或多个）
        timeout: Tuple[float, float] = (5.0, 5.0),  # 超时设置（连接超时, 读取超时）
        retry_count: int = 3  # 重试次数
    ):
        """
        初始化企业微信机器人通知
        
        :param wechat_keys: 企业微信机器人的key（单个字符串或字符串列表）
                           每个key对应一个机器人，可在机器人设置中获取
        :param timeout: 网络请求超时时间（元组格式，(连接超时秒数, 读取超时秒数)），默认(5,5)
        :param retry_count: 请求失败后的重试次数，默认3次（包含首次请求，实际重试retry_count-1次）
        """
        # 处理企微机器人key，生成完整webhook地址
        if isinstance(wechat_keys, str):
            # 单个key：去重空格后生成URL
            key = wechat_keys.strip()
            self.webhook_urls = [self._WEBHOOK_PREFIX + key] if key else []
        elif isinstance(wechat_keys, list):
            # 多个key：过滤空值后生成URL列表
            self.webhook_urls = [
                self._WEBHOOK_PREFIX + key.strip() 
                for key in wechat_keys 
                if key.strip()  # 跳过空字符串
            ]
        else:
            raise ValueError("企微机器人key必须是字符串或字符串列表")
        
        # 验证生成的webhook地址不为空
        if not self.webhook_urls:
            raise ValueError("企微机器人key不能为空（或全为空字符串）")
        
        # 验证超时参数（保持原有逻辑）
        if not isinstance(timeout, tuple) or len(timeout) != 2:
            raise ValueError("超时参数必须是元组格式：(连接超时, 读取超时)")
        if not all(isinstance(t, (int, float)) and t > 0 for t in timeout):
            raise ValueError("超时时间必须是正数")
        
        # 验证重试次数（保持原有逻辑）
        if not isinstance(retry_count, int) or retry_count < 1:
            raise ValueError("重试次数必须是大于等于1的整数")
        
        # 保存参数
        self.timeout = timeout
        self.retry_count = retry_count
        self.wechat_keys = wechat_keys  # 保留原始key（可选，用于调试）
        
        # 调试信息
        # print(f"初始化企业微信通知：机器人数量={len(self.webhook_urls)}，超时={timeout}秒，重试次数={retry_count}")
    
    def send_text(self, content: str, mentioned_mobile_list: List[str] = None) -> bool:
        """发送文本消息到所有机器人"""
        if not content:
            print("调试：消息内容不能为空，发送失败")
            return False
            
        data = {
            "msgtype": "text",
            "text": {
                "content": content
            }
        }
        
        if mentioned_mobile_list:
            data["text"]["mentioned_mobile_list"] = mentioned_mobile_list
        
        return self._send_request(data)
    
    def send_markdown(self, content: str, mentioned_mobile_list: List[str] = None) -> bool:
        """发送Markdown格式消息到所有机器人"""
        if not content:
            print("调试：Markdown内容不能为空，发送失败")
            return False
            
        data = {
            "msgtype": "markdown",
            "markdown": {
                "content": content
            }
        }

        if mentioned_mobile_list:
            data["mentioned_mobile_list"] = mentioned_mobile_list

        return self._send_request(data)
    
    def send_textcard(
        self,
        title: str,
        description: List[Tuple[str, str]],  # 保持你习惯的参数名description
        url: Optional[str] = None,
        btntxt: Optional[str] = None
    ) -> bool:
        """
        发送模拟文本卡片（支持normal颜色+修复属性错误）
        
        :param title: 卡片标题（必填）
        :param description: 颜色文本列表，格式：[(颜色类型, 文本内容), ...]
                           支持颜色：
                           - comment: 灰色
                           - info: 蓝色
                           - warning: 橙红色
                           - normal: 默认黑色（无额外标签）
        :param url: 跳转链接（可选）
        :param btntxt: 按钮文字（可选，默认"详情"）
        :return: 发送结果（bool）
        """
        # 基础校验
        if not title.strip():
            print("调试：卡片标题不能为空")
            return False
        if not isinstance(description, list) or len(description) == 0:
            print("调试：description必须是非空列表")
            return False

        # 核心：解析元组，转换为企微样式（支持normal）
        processed_lines = []
        for item in description:
            # 校验元组格式（必须是2个元素）
            if not isinstance(item, tuple) or len(item) != 2:
                print(f"调试：跳过无效格式项（需是(颜色, 文本)元组）：{item}")
                continue
            
            color, text = item[0].strip().lower(), item[1].strip()
            # 校验文本非空
            if not text:
                print("调试：跳过空文本项")
                continue
            
            # 处理不同颜色
            if color not in self._SUPPORTED_COLORS:
                # 无效颜色：按默认黑色显示，打印警告
                print(f"调试：跳过不支持的颜色「{color}」，仅支持{self._SUPPORTED_COLORS}")
                processed_lines.append(text)
            elif color == "normal":
                # normal：默认黑色，不添加颜色标签
                processed_lines.append(text)
            else:
                # 其他支持的颜色：拼接企微语法
                processed_lines.append(f"<font color=\"{color}\">{text}</font>")

        # 构造Markdown内容
        markdown_content = [
            f"# **{title.strip()}**",  # 标题加粗居中
            # "---",  # 分隔线
            "\n".join(processed_lines)  # 换行分隔文本
        ]

        # 处理链接和按钮
        url_clean = url.strip() if (url and url.strip()) else ""
        if url_clean:
            if url_clean.startswith(("http://", "https://")):
                btn_clean = btntxt.strip() if (btntxt and btntxt.strip()) else "详情"
                markdown_content.append(f"\n[🔗 {btn_clean}]({url_clean})")
            else:
                print("调试：跳转链接必须以http/https开头，跳过按钮")

        return self.send_markdown("\n".join(markdown_content))
    
    def _send_request(self, data: dict) -> bool:
        """发送请求到所有企业微信机器人API（支持重试）"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"{current_time} 即将发送企微消息：\n{data}")
        results = []
        for url in self.webhook_urls:
            success = False
            for attempt in range(1, self.retry_count + 1):
                try:
                    response = requests.post(
                        url,
                        headers={"Content-Type": "application/json"},
                        data=json.dumps(data),
                        timeout=self.timeout
                    )
                    
                    result = response.json()
                    if result.get("errcode") == 0:
                        success = True
                        break
                    else:
                        print(f"调试：第{attempt}次尝试失败（{url}）: 错误信息：{result.get('errmsg')}")
                        
                except Exception as e:
                    print(f"调试：第{attempt}次尝试异常（{url}）: 异常信息：{str(e)}")
                
                if attempt < self.retry_count:
                    time.sleep(1)
            
            results.append(success)
        
        success_count = sum(results)
        fail_count = len(results) - success_count
        # print(f"调试：所有机器人发送完成，成功{success_count}个，失败{fail_count}个")
        
        return any(results)
    
    def send(self, message: str, mentioned_mobile_list: List[str] = None) -> bool:
        """实现基类的send方法，默认发送文本消息"""
        return self.send_text(message, mentioned_mobile_list)


if __name__ == "__main__":

    wechat_keys = ['xxxxxxxxxxx']  # 填写企业微信的webhook密钥，多个以逗号分隔

    wechat_notify = WeChatNotification(wechat_keys=wechat_keys)

    # 发送普通文本
    wechat_notify.send_text("直接发送普通文本")

    # 发送markdown文本
    wechat_notify.send_markdown(f"info: <font color=\"info\">2025年11月20日 9:00-11:00</font>")
    wechat_notify.send_markdown(f"comment: <font color=\"comment\">2025年11月20日 9:00-11:00</font>")
    wechat_notify.send_markdown(f"warning: <font color=\"warning\">2025年11月20日 9:00-11:00</font>")

    wechat_notify.send_markdown("""
        ### 📢 【系统升级维护通知】
        #### 维护信息
        - 维护时间：<font color="warning">2025-11-21 00:00-02:00</font>（2小时）
        - 影响范围：所有线上服务（Web端、APP端、接口）
        - 维护目的：服务器扩容+安全补丁更新

        #### 注意事项
        1. 维护期间无法登录/操作系统，请提前完成关键工作
        2. 已下单未支付的订单将保留至维护结束后24小时
        3. 如有紧急问题，请联系值班人员：<font color="info">138xxxx8888</font>

        #### 后续通知
        - 维护完成后将通过本机器人推送恢复通知
        - 详细维护报告将在次日10:00前发送至企业邮箱
    """)


    # 发送卡片消息（通过markdown模拟）
    wechat_notify.send_textcard(
        title="系统通知",
        description=[
            ("comment", "灰色文本：操作日志 - 2025-11-20 09:00"),
            ("info", "蓝色文本：正常提醒 - 系统运行稳定"),
            ("warning", "橙红色文本：异常提醒 - 数据库连接波动"),
            ("normal", "常规文本：操作日志 - 2025-11-20 10:00")
        ],
        url="https://xxx.com/日志详情",
        btntxt="查看完整日志"
    )


    wechat_notify.send_markdown("""
        ## 点击打开  [必应首页](https://cn.bing.com/?mkt=zh-CN)
    """)
