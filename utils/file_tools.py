# -*- coding: utf-8 -*-
import os
import time
import shutil

class FileTools:
    @staticmethod
    def copy_file(temp_file_dir, save_full_path):
        """
        等待临时目录中出现文件，并将其复制到指定路径
        """
        print(f"正在等待文件下载至: {temp_file_dir}")
        max_wait = 60
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            if not os.path.exists(temp_file_dir):
                time.sleep(1)
                continue
                
            files = os.listdir(temp_file_dir)
            # 过滤掉临时文件（根据需要调整后缀）
            valid_files = [f for f in files if not f.endswith('.tmp') and not f.endswith('.crdownload')]
            
            if valid_files:
                # 假设只有一个文件，或者取最新的一个
                source_file = os.path.join(temp_file_dir, valid_files[0])
                
                # 确保目标目录存在
                os.makedirs(os.path.dirname(save_full_path), exist_ok=True)
                
                # 复制文件
                shutil.copy2(source_file, save_full_path)
                print(f"文件已复制: {source_file} -> {save_full_path}")
                return True
                
            time.sleep(1)
        
        print(f"超时：在 {temp_file_dir} 中未找到下载文件")
        return False

    @staticmethod
    def clear_directory(directory):
        """
        清空指定目录下的所有文件和子目录
        """
        print(f"正在清空目录: {directory}")
        if not os.path.exists(directory):
            print(f"目录不存在: {directory}")
            return

        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                    print(f"已删除文件: {file_path}")
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
                    print(f"已删除目录: {file_path}")
            except Exception as e:
                print(f'删除 {file_path} 失败. 原因: {e}')
        print(f"目录清空完成: {directory}")

    @staticmethod
    def path_exists(path):
        if not isinstance(path, str):
            path = str(path)
        exists = os.path.exists(path)
        print(f"路径存在检查: {path} -> {exists}")
        return exists
