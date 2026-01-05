import platform
import subprocess
import sys
import os
import tkinter as tk
from tkinter import filedialog
from PyQt5.QtCore import QObject, pyqtSignal


class CmdOutputSignal(QObject):
    # 定义信号，携带实时输出字符串
    realtime_output = pyqtSignal(str)


global_cmd_signal = CmdOutputSignal()


def run_cmd(command, description="描述", shell=False, capture_output=True, text=True, input=None, check=True):
    """
    使用 subprocess.run 执行命令的辅助函数
    :param command: 要执行的命令（列表或字符串）
    :param description: 命令的描述，用于打印日志（默认值："描述"）
    :param shell: 传递的是列表，直接执行命令，不通过shell解析（默认值：False）
    :param capture_output: 捕获输出，存储在返回对象的stdout和stderr属性中（默认值：True）
    :param text: 输出为文本字符串（str对象）（默认值：True）
    :param input: text=True，则应该是字符串（默认值：None）
    :param check: 是否检查命令执行是否成功只要子进程 返回码 ≠ 0，立即抛 subprocess.CalledProcessError（默认值：True）
    :return: subprocess.CompletedProcess 实例，包含 returncode stdout stderr
    """
    print(f"正在{description}...")
    try:
        result = subprocess.run(
            command,
            shell=shell,
            capture_output=capture_output,
            text=text,
            input=input,
            check=check,
            encoding='utf-8'
        )
        if capture_output and result.stdout:
            print(f"输出: {result.stdout}")
        return result
    except subprocess.CalledProcessError as e:
        print(f"{description}失败: {e}")
        if e.stderr:
            print(f"错误信息: {e.stderr}")
        return subprocess.CompletedProcess(
            args=command,
            returncode=e.returncode,
            stdout=e.stdout or '',
            stderr=e.stderr or ''
        )


def run_cmd_popen(command, description='描述', shell=False, capture_output=True, text=True, input=None, check=True,
                  progress_callback=None):
    """
    使用 subprocess.Popen 执行命令的辅助函数, 支持实时进度回调
    :param command: 要执行的命令（列表或字符串）
    :param description: 命令的描述，用于打印日志（默认值："描述"）
    :param shell: 传递的是字符串，直接执行命令，不通过shell解析（默认值：False）
    :param capture_output: 捕获输出，存储在返回对象的stdout和stderr属性中（默认值：True）
    :param text: 输出为文本字符串（str对象）（默认值：True）
    :param input: text=True，则应该是字符串（默认值：None）
    :param check: 是否检查命令执行是否成功失败会抛出subprocess.CalledProcessError异常（默认值：True）
    :param progress_callback: 进度更新回调函数，用于实时显示进度（默认值：None）
    :return: subprocess.Popen 实例
    """
    print(f"正在{description}...")
    if check:
        try:
            process = subprocess.Popen(
                command,
                shell=shell,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=text,
                encoding='utf-8'
            )
            stdout_lines = []
            stderr_lines = []
            # 实时读取输出，有数据就发送信号
            while True:
                output = process.stdout.readline()  # 阻塞读取一行含\n
                # poll() 进程结束返回退出状态码立即退出while循环并没有对output进行处理，否则返回None
                if output == '' and process.poll() is not None:
                    break
                if output:
                    output_line = output.strip()  # 去掉行首尾空白/换行
                    print(output_line)
                    stdout_lines.append(output)
                    # 处理进度回调 检测该对象是否有emit方法
                    if progress_callback is not None and hasattr(progress_callback, 'emit'):
                        # 发送实时输出到信号槽
                        progress_callback.emit(output_line)
                    elif callable(progress_callback):
                        progress_callback(output_line)

            # 处理进程结束后的output 获取剩余的输出和错误
            stdout, stderr = process.communicate()
            stdout_lines.append(stdout)
            stderr_lines.append(stderr)

            result = subprocess.CompletedProcess(
                args=command,
                returncode=process.returncode,
                stdout=''.join(stdout_lines),
                stderr=''.join(stderr_lines)
            )

            if result.stderr:
                print(f"错误信息: {result.stderr}")
                if progress_callback is not None and hasattr(progress_callback, 'emit'):
                    progress_callback.emit(result.stderr)

            return result

        except subprocess.CalledProcessError as e:
            print(f"{description}失败: {e}")
            if e.stderr:
                print(f"错误信息: {e.stderr}")
                sys.exit(1)


# 获取远程主机的指纹
def get_remote_host_fingerprint(username, host_ip, password):
    """
    获取远程主机的指纹
    (plink -batch -ssh trex@192.168.31.89 -pw "123" 2>&1) -match 'SHA256' | Select-Object -Last 1
    plink -batch -ssh trex@192.168.31.89 -pw "123" "cd ~ && pwd" 2>&1 | findstr "SHA256"
    :param username: 用户名
    :param host_ip: 主机IP
    :param password: 密码
    :return: 远程主机的指纹
    """
    plink_cmd_str = (f'(plink -batch -ssh {username}@{host_ip} -pw "{password}" 2>&1) -match "SHA256" | '
                     f'Select-Object -Last 1')
    # plink_cmd_str = f'plink -batch -ssh {username}@{host_ip} -pw "{password}" "cd ~ && pwd" 2>&1 | findstr "SHA256"'
    plink_cmd = [
        "powershell",
        "-Command",
        plink_cmd_str
    ]
    print(plink_cmd)
    ret = run_cmd(plink_cmd, description="获取远程主机指纹", shell=True, check=False)
    if ret and hasattr(ret, 'stdout') and ret.stdout:
        fingerprint = ret.stdout.strip()[-1]
        if fingerprint == 'False':
            print("获取远程主机指纹失败: 连接有误")
            return None
    elif ret and hasattr(ret, 'stderr'):
        fingerprint = ret.stderr.strip().split()[-1]
        print(f"远程主机指纹: {fingerprint}")
        return fingerprint
    else:
        print("获取远程主机指纹失败: 无返回结果")
        return None


def get_detailed_platform_info():
    return {
        "system": platform.system(),  # Windows, Linux, Darwin等
        "release": platform.release(),  # 操作系统版本
        "version": platform.version(),  # 详细版本信息
        "machine": platform.machine(),  # 机器类型，如x86_64
        "processor": platform.processor()  # 处理器信息
    }


def connect_transmit(username, host_ip, password, src_path, dst_path="~/tempTest", progress_signal=None):
    """
    连接到主机并执行命令
    :param progress_signal:
    :param username: 主机登录用户名
    :param host_ip: 主机地址（IP或域名）
    :param password: 主机登录密码
    :param src_path: 本地文件路径（可选）
    :param dst_path: 远程主机文件路径（可选）
    :return: subprocess.CompletedProcess 实例，包含 returncode stdout stderr
    """
    print(get_detailed_platform_info())
    if platform.system() == "Windows":
        run_cmd(
            ["powershell", "-Command", "Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force"],
            "设置 PowerShell 执行策略"
        )
        if not os.path.exists(os.path.expanduser("~\\scoop")):
            run_cmd(
                ["powershell", "-Command", "irm get.scoop.sh | iex"],
                "安装 Scoop 包管理器"
            )
        else:
            print("Scoop 已安装，跳过安装步骤")
        # run_cmd(["scoop", "-V"], "检查 Scoop 版本")
        if not os.path.exists(os.path.expanduser("~\\scoop\\apps\\putty")):
            run_cmd(["powershell", "-Command", f"scoop install putty"], "安装 PuTTY")
        else:
            print("PuTTY 已安装，跳过安装步骤")
        # [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
        run_cmd(
            ["powershell", "-Command", "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8"],
            "设置 PowerShell 输出编码为 UTF-8"
        )
    elif platform.system() == "Linux":
        pass
    # 获取远程主机的指纹
    fingerprint = get_remote_host_fingerprint(username, host_ip, password)
    if not fingerprint:
        print("获取远程主机指纹失败")
    # 获取用户家目录
    if dst_path.endswith("/"):
        dst_dir = dst_path.split("/")[-2]
    else:
        dst_dir = dst_path.split("/")[-1]
    if dst_path[0] == "~":
        # linux-linux echo y | plink -ssh -noagent trex@192.168.31.87 -pw "123" "cd ~ && pwd"
        plink_cmd_str = f"plink -batch -ssh -hostkey {fingerprint} {username}@{host_ip} -pw \"{password}\" \"cd ~ && pwd\""
        print(plink_cmd_str)
        plink_result = run_cmd(plink_cmd_str, description="获取用户家目录")
        # strip 移除字符串首尾的空白符（包括空格、制表符、换行符等）
        dst_path = plink_result.stdout.strip() + "/" + dst_dir

    pscp_cmd_str = f"pscp -batch -hostkey {fingerprint} -pw \"{password}\" {src_path} {username}@{host_ip}:{dst_path}"
    print(pscp_cmd_str)
    pscp_cmd = [
        "powershell", "-Command",
        pscp_cmd_str
    ]
    plink_result = run_cmd_popen(pscp_cmd, description="上传文件", progress_callback=progress_signal)
    # plink_result = run_cmd(pscp_cmd, description="上传文件")
    return plink_result


def connect_execute(username, host_ip, password, src_path, dst_path="~/tempTest"):
    """
    连接到主机并执行命令
    :param username: 主机登录用户名
    :param host_ip: 主机地址（IP或域名）
    :param password: 主机登录密码
    :param src_path: 本地文件路径（可选）
    :param dst_path: 远程主机文件路径（可选）
    :return: subprocess.CompletedProcess 实例，包含 returncode stdout stderr
    """
    run_cmd(
        ["powershell", "-Command", "Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force"],
        "设置 PowerShell 执行策略"
    )
    if not os.path.exists(os.path.expanduser("~\\scoop")):
        run_cmd(
            ["powershell", "-Command", "irm get.scoop.sh | iex"],
            "安装 Scoop 包管理器"
        )
    else:
        print("Scoop 已安装，跳过安装步骤")
    # run_cmd(["scoop", "-V"], "检查 Scoop 版本")
    if not os.path.exists(os.path.expanduser("~\\scoop\\apps\\putty")):
        run_cmd(["powershell", "-Command", f"scoop install putty"], "安装 PuTTY")
    else:
        print("PuTTY 已安装，跳过安装步骤")
    # [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    run_cmd(
        ["powershell", "-Command", "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8"],
        "设置 PowerShell 输出编码为 UTF-8"
    )
    pscp_cmd_str = f"echo \"y\" | pscp -pw \"{password}\" {src_path} {username}@{host_ip}:{dst_path}"
    print(pscp_cmd_str)
    pscp_cmd = [
        "powershell", "-Command",
        pscp_cmd_str
    ]
    filename = src_path.split("\\")[-1]  # 返回一个列表，取最后一个元素
    if dst_path.endswith("/"):
        path_name = dst_path + filename
    else:
        path_name = dst_path + "/" + filename
    # c -t uisrc @ 192.168.31.10 "LANG=en_US.UTF-8; chmod +x ~/ACL.sh && ~/ACL.sh"
    plink_cmd_str = f"plink -batch -n -pw \"{password}\" -ssh -noagent -t {username}@{host_ip} \"LANG=en_US.UTF-8; chmod +x {path_name} && echo \"{password}\" | sudo -S {path_name}\""
    print(plink_cmd_str)
    plink_cmd = [
        "powershell", "-Command",
        plink_cmd_str
    ]
    run_cmd(pscp_cmd, description="上传文件")  # 可输出当前时间，以及传输进度，上传成功后提示
    plink_result = run_cmd(plink_cmd, description="执行命令")
    return plink_result


def select_file_dialog(title="选择文件", filetypes=None):
    """
    打开文件选择对话框，选择本地文件
    :param title: 对话框标题（默认值："选择文件"）
    :param filetypes: 文件类型筛选器列表，每个元素为元组 (描述, 模式)（默认值：None，显示所有文件）
    :return: 选中的文件路径（字符串），如果取消选择则为空字符串
    """
    root = tk.Tk()
    root.withdraw()
    if filetypes is None:
        filetypes = [("All Files", "*.*")]
    file_path = filedialog.askopenfilename(title=title, filetypes=filetypes)
    return file_path


def main():
    src_path = select_file_dialog()
    ret = connect_execute("trex", "192.168.31.87", "123", src_path)
    if ret.returncode == 0:
        print("命令执行成功")
    else:
        print(f"命令执行失败，返回码：{ret.returncode}")


# 如果直接运行此脚本（而不是作为模块导入），则执行main()函数
# 模块导入时不执行main()函数
if __name__ == "__main__":
    main()
