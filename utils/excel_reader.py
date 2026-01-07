# 标准库
import os

# 三方库
import argparse
import pandas as pd

class ExcelReader:
    """Excel文件读取工具类（基于pandas实现）"""
    
    def __init__(self):
        self.file_path = None  # 改为open方法赋值
        self.data = None  # 存储当前sheet的数据
        self.sheet_names = None  # 所有sheet名称
        self.active_sheet_name = None  # 当前激活的sheet名称
        self.row_count = 0  # 行数
        
    def open(self, file_path):  # 新增file_path参数
        """打开Excel文件并读取数据"""
        self.file_path = file_path  # 赋值给实例变量
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"文件不存在: {self.file_path}")
            
        try:
            # 获取所有sheet名称
            self.sheet_names = pd.ExcelFile(self.file_path).sheet_names
            # 默认激活第一个sheet
            self.active_sheet_name = self.sheet_names[0]
            
            # 读取当前激活的sheet数据
            self.data = pd.read_excel(
                self.file_path,
                sheet_name=self.active_sheet_name,
                header=None  # 不将第一行作为表头，保持原始数据结构
            )
            
            # 获取行数（pandas会忽略全空行，所以与openpyxl可能有差异）
            self.row_count = self.data.shape[0]
            return True
        except Exception as e:
            print(f"打开文件失败: {str(e)}")
            return False
    
    def get_active_sheet_name(self):
        if self.active_sheet_name is None:
            raise Exception("请先调用open()方法打开文件")
        return self.active_sheet_name
    
    def get_row_count(self):
        if self.data is None:
            raise Exception("请先调用open()方法打开文件")
        return self.row_count
    
    def get_cell_value(self, cell_identifier):
        """
        获取指定单元格的值，支持两种格式：
        1. A1格式，如"A1"
        2. 列,行格式，如"Z,19710"（列,行）
        """
        if self.data is None:
            raise Exception("请先调用open()方法打开文件")
        
        try:
            # 解析单元格标识符
            if ',' in cell_identifier:
                # 处理"列,行"格式
                col_part, row_part = cell_identifier.split(',')
                row = int(row_part.strip()) - 1  # pandas索引从0开始
                col_part = col_part.strip()
            else:
                # 处理"A1"格式
                col_str = ''
                row_str = ''
                for c in cell_identifier:
                    if c.isalpha():
                        col_str += c
                    else:
                        row_str += c
                row = int(row_str) - 1  # pandas索引从0开始
                col_part = col_str.upper()
            
            # 转换列标识符为数字索引（A=0, B=1, ..., Z=25, AA=26等）
            col = 0
            for c in col_part:
                col = col * 26 + (ord(c.upper()) - ord('A') + 1)
            col -= 1  # 转换为0-based索引
            
            # 检查行和列是否在有效范围内
            if row < 0 or row >= self.row_count:
                raise IndexError(f"行号超出范围，有效行范围: 1-{self.row_count + 1}")
            
            if col < 0 or col >= self.data.shape[1]:
                raise IndexError(f"列号超出范围，有效列范围: 1-{self.data.shape[1]}")
            
            # 获取单元格值
            cell_value = self.data.iloc[row, col]
            
            # pandas会将空单元格显示为NaN，这里统一转换为None
            return cell_value if pd.notna(cell_value) else None
        except Exception as e:
            print(f"获取单元格值失败: {str(e)}")
            return None
    
    def close(self):
        # pandas不需要显式关闭文件，但可以清理变量
        self.data = None
        self.sheet_names = None
        self.active_sheet_name = None
        self.row_count = 0
        self.file_path = None  # 清理文件路径

    # 支持上下文管理器（with语句）
    def __enter__(self):
        # 注意：上下文管理器模式下，需先调用open()传入file_path，或修改为在__enter__传参
        # 保持原有逻辑不变，使用时需先调用open
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description='读取Excel文件信息')
    parser.add_argument('file_path', help='Excel文件的路径')
    parser.add_argument('--cell', help='要读取的单元格，如"A1"或"Z,19710"（列,行）', default='A1')
    
    args = parser.parse_args()
    
    # 调整为：先创建实例，再调用open传入file_path（保持上下文管理器兼容）
    try:
        reader = ExcelReader()
        with reader:
            if reader.open(args.file_path):  # 传入file_path参数
                print(f"成功打开文件: {args.file_path}")
                print(f"激活的sheet: {reader.get_active_sheet_name()}")
                print(f"总行数: {reader.get_row_count()}")
                
                cell_value = reader.get_cell_value(args.cell)
                print(f"单元格 {args.cell} 的值: {cell_value}")
    except Exception as e:
        print(f"发生错误: {str(e)}")