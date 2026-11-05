import os
import shutil

class PluginManager:
    def __init__(self, log_func, update_status_func):
        self.log = log_func
        self.update_status = update_status_func

    def install_jassdebug(self, war3_path, base_dir):
        if not war3_path or not os.path.exists(war3_path):
            self.log("[-] 错误: 未设置有效的魔兽目录，无法安装插件。")
            self.update_status("安装失败: 目录无效")
            return False

        src_plugin = os.path.join(base_dir, "plugins", "JassDebug.asi")
        if not os.path.exists(src_plugin):
            self.log(f"[-] 错误: 找不到源文件 {src_plugin}")
            self.update_status("安装失败: 源文件缺失")
            return False

        try:
            # 目标路径通常是魔兽根目录或其下的 plugins 文件夹
            # 为了最大兼容性，我们直接复制到根目录，并提醒用户需要 ASI Loader
            dst_plugin = os.path.join(war3_path, "JassDebug.asi")
            shutil.copy2(src_plugin, dst_plugin)
            
            self.log(f"[+] 插件已安装至: {dst_plugin}")
            self.log("[提示] 请确保您的魔兽目录包含 ASI Loader (如 version.dll)。")
            self.log("[提示] 如果是 1.27+ 版本，建议将插件放在魔兽根目录。")
            self.update_status("JassDebug 安装成功")
            return True
        except Exception as e:
            self.log(f"[-] 安装插件失败: {e}")
            self.update_status("安装失败")
            return False

    def uninstall_jassdebug(self, war3_path):
        if not war3_path or not os.path.exists(war3_path):
            self.log("[-] 错误: 未设置有效的魔兽目录，无法卸载插件。")
            self.update_status("卸载失败: 目录无效")
            return False

        try:
            target_files = [
                os.path.join(war3_path, "JassDebug.asi"),
                os.path.join(war3_path, "plugins", "JassDebug.asi") # 检查子目录
            ]
            
            removed = False
            for f in target_files:
                if os.path.exists(f):
                    os.remove(f)
                    self.log(f"[+] 已移除插件文件: {f}")
                    removed = True
            
            if removed:
                self.update_status("JassDebug 卸载成功")
            else:
                self.log("[-] 未在魔兽目录中找到已安装的 JassDebug 插件。")
                self.update_status("未发现插件")
            return True
        except Exception as e:
            self.log(f"[-] 卸载插件失败: {e}")
            self.update_status("卸载失败")
            return False
