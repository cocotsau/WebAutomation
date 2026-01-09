from core.engine import Engine
from tools.basic_tools import PrintLogAction, DelayAction, SetVariableAction, FileDialogAction, InputDialogAction, CalculateAction
from tools.excel_tools import OpenExcelAction, ReadExcelAction, GetExcelRowCountAction, WriteExcelAction, SaveExcelAction, CloseExcelAction
from tools.logic_tools import WhileAction
from tools.util_tools import ExtractContentAction
import sys
from PySide6.QtWidgets import QApplication
from gui.main_window import FlowManagerWindow

# Registry of available tools
TOOL_REGISTRY = {
    "PrintLog": PrintLogAction,
    "Delay": DelayAction,
    "SetVariable": SetVariableAction,
    "FileDialog": FileDialogAction,
    "InputDialog": InputDialogAction,
    "Calculate": CalculateAction,
    "OpenExcel": OpenExcelAction,
    "ReadExcel": ReadExcelAction,
    "GetExcelRowCount": GetExcelRowCountAction,
    "WriteExcel": WriteExcelAction,
    "SaveExcel": SaveExcelAction,
    "CloseExcel": CloseExcelAction,
    "While": WhileAction,
    "ExtractContent": ExtractContentAction
}

def main():
    # Workflow optimized based on screenshot
    workflow_data = [
        # 1. Set Pattern (Regex for Douyin short link)
        {"tool_name": "SetVariable", "params": {"key": "pattern", "value": r"https://v\.douyin\.com/[a-zA-Z0-9]+/"}},
        
        # 2. Set Loop Current (Start from row 2)
        {"tool_name": "SetVariable", "params": {"key": "loop_current", "value": 2}},
        
        # 3. Select Excel File
        {"tool_name": "FileDialog", "params": {"prompt": "请选择excel文件", "output_variable": "excel_path"}},
        
        # 4. Log Selected File
        {"tool_name": "PrintLog", "params": {"message": "Selected file: {excel_path}"}},
        
        # 5. Input Read Column (e.g., A)
        {"tool_name": "InputDialog", "params": {"prompt": "输入读取抖音短链接的列, 如: A", "output_variable": "column_read"}},
        
        # 6. Input Save Column (e.g., B)
        {"tool_name": "InputDialog", "params": {"prompt": "输入保存抖音视频id的列, 如: B", "output_variable": "column_save"}},
        
        # 7. Log Columns
        {"tool_name": "PrintLog", "params": {"message": "Read Col: {column_read}, Save Col: {column_save}"}},
        
        # 8. Open Excel (data_only=False to preserve structure if saving back)
        {"tool_name": "OpenExcel", "params": {"file_path": "{excel_path}", "alias": "excel_instance", "data_only": False}},
        
        # 9. Get Total Rows
        {"tool_name": "GetExcelRowCount", "params": {"alias": "excel_instance", "output_variable": "excel_row_count"}},
        
        # 10. Log Row Count
        {"tool_name": "PrintLog", "params": {"message": "Total Rows: {excel_row_count}"}},
        
        # 11. While Loop (Iterate through rows)
        {
            "tool_name": "While",
            "params": {
                "condition": "loop_current <= excel_row_count",
                "children": [
                    # 12. Log Loop Info
                    {"tool_name": "PrintLog", "params": {"message": "Processing Row {loop_current}, Col {column_read}"}},
                    
                    # 13. Read Cell Content
                    {"tool_name": "ReadExcel", "params": {
                        "alias": "excel_instance", 
                        "read_type": "Cell", 
                        "address": "{column_read}{loop_current}", 
                        "output_variable": "cell_value"
                    }},
                    
                    # 14. Extract Content (Regex)
                    {"tool_name": "ExtractContent", "params": {
                        "text": "{cell_value}", 
                        "pattern": "{pattern}", 
                        "output_variable": "extracted_value"
                    }},
                    
                    # 15. Log Extracted Value
                    {"tool_name": "PrintLog", "params": {"message": "Extracted: {extracted_value}"}},
                    
                    # 16. Write Result (Optimization: Save extracted ID/Link)
                    {"tool_name": "WriteExcel", "params": {
                        "alias": "excel_instance",
                        "write_type": "Cell",
                        "address": "{column_save}{loop_current}",
                        "value": "{extracted_value}"
                    }},
                    
                    # 17. Increment Loop Counter
                    {"tool_name": "Calculate", "params": {"expression": "loop_current + 1", "output_variable": "loop_current"}}
                ]
            }
        },
        
        # 18. Save Excel
        {"tool_name": "SaveExcel", "params": {"alias": "excel_instance"}},
        
        # 19. Close Excel
        {"tool_name": "CloseExcel", "params": {"alias": "excel_instance"}},
        
        # 20. Done
        {"tool_name": "PrintLog", "params": {"message": "Automation finished."}}
    ]

    engine = Engine()
    engine.load_workflow(workflow_data, TOOL_REGISTRY)
    engine.run()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1].lower() == "cli":
        main()
    else:
        app = QApplication(sys.argv)
        win = FlowManagerWindow()
        win.show()
        sys.exit(app.exec())
