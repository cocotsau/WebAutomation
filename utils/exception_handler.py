import traceback


class ExceptionHandler:
    """业务异常处理工具类"""

    @staticmethod
    def handle(e: Exception) -> dict:
        """
        核心静态方法：处理异常并返回统一格式响应
        :param e: 捕获的异常对象
        """
        try:
            stack_info = traceback.format_exc()
        except Exception as fe:
            stack_info = f"堆栈格式化失败: {fe!r}"
        if stack_info and len(stack_info) > 1500:
            stack_info = stack_info[:1500] + "\n...（堆栈信息过长，已截断）"

        error_msg = (
            "\n======= 流程内部异常 ======="
            f"\n错误类型：{type(e).__name__}"
            # f"\n错误信息：{str(e)}"
            "\n错误堆栈（定位具体代码行）：\n"
            f"{stack_info}"
            "\n==========================="
        )
        print(error_msg)
        return error_msg

        

    @staticmethod
    def build_error_msg(title: str, tips : str, e: Exception) -> str:
        msg_parts = []
        msg_parts.append(title)
        msg_parts.append(tips)
        msg_parts.append("```")
        msg_parts.append(ExceptionHandler.handle(e))
        msg_parts.append("```")
        return "\n".join(msg_parts)
