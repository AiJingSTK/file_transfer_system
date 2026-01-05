import sys
import os  # 与操作系统交互的功能，包括文件系统操作、进程管理等

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (QApplication, QWidget, QLineEdit,
                             QFileDialog, QMessageBox, QProgressBar,
                             QLabel, QProgressDialog, )
import putty_script

import File_transfer_system as fts
from File_transfer_system import Ui_mainWindow
from progress_bar_dialog import Ui_Dialog


# 进度条弹窗类
class ProgressBarDialog(QWidget, Ui_Dialog):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        # 添加进度条和状态标签
        self.progressBar = QProgressBar(self)
        self.progressBar.setGeometry(20, 200, 200, 25)
        self.progressBar.setRange(0, 100)
        self.progressBar.setValue(0)
        self.status_label = QLabel(self)
        self.status_label.setGeometry(20, 230, 200, 20)
        self.status_label.setText("Ready")


class TransmitThread(QThread):
    """
        线程类，用于在后台执行文件传输操作
    """
    # 定义信号，携带进度更新消息，用于在进度更新时通知主线程
    progress_signal = pyqtSignal(str)
    # 定义信号，携带传输结果对象，用于在线程完成时通知主线程
    finished_signal = pyqtSignal(object)

    def __init__(self, username, host_ip, password, src_path, dst_path="~/tempTest"):
        super().__init__()
        self.username = username
        self.host_ip = host_ip
        self.password = password
        self.src_path = src_path
        self.dst_path = dst_path

    def run(self):
        """
            重写run方法 线程运行方法，用于执行文件传输操作
        :return: None
        """
        ret = putty_script.connect_transmit(
            self.username, self.host_ip, self.password,
            self.src_path, self.dst_path,
            progress_signal=self.progress_signal
        )
        # ret = putty_script.connect_transmit(
        #     self.username, self.host_ip, self.password,
        #     self.src_path, self.dst_path
        # )
        self.finished_signal.emit(ret)  # 发送信号携带传输结果对象


class MainWindow(QWidget, Ui_mainWindow):
    def __init__(self):
        super().__init__()
        # 给界面对象添加组件
        self.setupUi(self)
        self.password_lineEdit.setEchoMode(QLineEdit.Password)
        # 发送信号连接到槽函数
        self.transmit_pushButton.clicked.connect(self.transmit_execute)
        self.uname_lineEdit.setText("trex")
        self.host_ip_lineEdit.setText("192.168.31.89")
        self.password_lineEdit.setText("123")
        self.progress_dialog = None
        self.transmit_thread = None

    def transmit_execute(self):
        # 从界面获取输入参数
        username = self.uname_lineEdit.text()
        host_ip = self.host_ip_lineEdit.text()
        password = self.password_lineEdit.text()
        if not username or not host_ip or not password:
            QMessageBox.warning(self, 'Warning', 'Please enter your username, IP address, and password')
            return
        # 根据操作系统自动使用正确的路径分隔符
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        print(f'desktop_path: {desktop_path}')
        while True:
            # 返回一个元组，第一个元素是文件路径，第二个元素是文件过滤字符串
            src_path = QFileDialog.getOpenFileName(self, 'Select Source File', "D:/AJ_aijing/10.慧网星联实验/")[0]
            if not src_path:
                ret = QMessageBox.warning(self, 'Warning', 'Please select a source file.',
                                          QMessageBox.Ok | QMessageBox.Cancel)
                if ret == QMessageBox.Cancel:
                    return
            else:
                break

        print(src_path)
        # 创建进度条弹窗
        self.progress_dialog = QProgressDialog("Transmitting...", "Cancel", 0, 100, self)
        self.progress_dialog.setWindowTitle("Transmit progress")
        self.progress_dialog.setWindowModality(Qt.WindowModal)  # 阻塞主窗口 必须先处理对话框
        self.progress_dialog.setMinimumDuration(0)  # 0ms后立即显示进度条
        self.progress_dialog.setValue(0)  # 初始化进度为0
        # 禁用取消按钮
        self.progress_dialog.setCancelButton(None)

        # 创建并启动传输线程
        self.transmit_thread = TransmitThread(username, host_ip, password, src_path)
        # 发送信号连接到槽函数
        self.transmit_thread.progress_signal.connect(self.progress_update)  # 连接进度更新信号到槽函数
        self.transmit_thread.finished_signal.connect(self.transmit_finished)
        self.transmit_thread.start()  # 启动线程 会自动调用run方法

        # 调用 putty_script 中的函数执行传输
        # ret = putty_script.connect_transmit(username, host_ip, password, src_path)

    def progress_update(self, message):
        """
        更新进度条和状态标签
        :param message: 接收到信号携带的进度更新消息
        :return:
        """
        self.progress_dialog.setLabelText(message)
        # 解析进度更新消息，提取进度值
        if "|" in message and "%" in message:
            try:
                # single_arm_routing.sh     | 4 kB |   4.0 kB/s | ETA: 00:00:00 |  59%
                parts = message.split("|")  # 按|分隔返回列表
                if len(parts) >= 4:
                    percent_str = parts[-1].strip()  # 移除首尾空格
                    percent = int(percent_str.replace("%", ""))  # 移除%符号并转换为整数
                    self.progress_dialog.setValue(percent)  # 更新进度条值
            except (ValueError, IndexError):
                pass  # 忽略解析错误

    def transmit_finished(self, ret):
        """
        槽函数，用于处理传输线程完成信号
        :param ret: 接收到信号携带的传输线程返回的结果对象
        :return:
        """
        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None

        if ret.returncode == 0:
            QMessageBox.information(self, 'Success', 'Transmit completed successfully')
        else:
            QMessageBox.warning(self, 'Warning', f"Transmit failed, return code: {ret.returncode}")


if __name__ == '__main__':
    # 创建应用程序实例 传入命令行参数
    app = QApplication(sys.argv)  # 提供了整个图形界面的底层管理功能（初始化，程序入口参数，事件等）
    # 创建主窗口实例
    main_window = MainWindow()
    main_window.show()  # 显示主窗口

    app.exec_()  # 进入主事件循环 等待用户交互事件发生
