# -*- coding: utf-8 -*-

import sys
import time

class TimeTools:

    @staticmethod
    def countdown(seconds: int = 3):
        """可视化倒计时：动态显示剩余时间（分:秒格式）"""
        if not (isinstance(seconds, int) and seconds > 0):
            raise ValueError("seconds 必须是大于0的整数（单位：秒）")
        try:
            remaining = seconds
            while remaining:
                mins, secs = divmod(remaining, 60)
                sys.stdout.write(f"\r⏳  剩余时间: {mins:02d}:{secs:02d}")
                sys.stdout.flush()
                time.sleep(1)
                remaining -= 1
            sys.stdout.write("\r" + " " * 30 + "\r")
            print(f"✅ 倒计时{seconds}秒完成")
        except Exception as e:
            raise Exception(f"倒计时执行失败：{str(e)}") from e