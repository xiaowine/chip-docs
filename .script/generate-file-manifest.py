import os
import json
import datetime
import hashlib
import uuid  # 添加uuid模块导入
import pytz  # 添加pytz模块用于时区支持
from pathlib import Path
from typing import List, Dict, Any, Union

# 定义北京时区
BEIJING_TZ = pytz.timezone('Asia/Shanghai')

def get_all_files(dir_path: str) -> List[Dict[str, Any]]:
    """
    递归获取指定目录下的所有文件和子目录信息，忽略.git文件夹
    
    Args:
        dir_path: 要扫描的目录路径
        
    Returns:
        包含文件信息的列表
    """
    array_of_files = []

    for item in os.listdir(dir_path):
        # 忽略.git文件夹
        if item == '.git':
            continue

        full_path = os.path.join(dir_path, item)
        stat = os.stat(full_path)

        # 如果是目录，递归获取子目录中的文件
        if os.path.isdir(full_path):
            array_of_files.extend(get_all_files(full_path))
            # 添加目录本身
            array_of_files.append({
                "path": full_path,
                "size": 0,
                "modifiedTime": datetime.datetime.fromtimestamp(stat.st_mtime, BEIJING_TZ).isoformat(),
                "isDirectory": True
            })
        else:
            # 添加文件
            array_of_files.append({
                "path": full_path,
                "size": stat.st_size,
                "modifiedTime": datetime.datetime.fromtimestamp(stat.st_mtime, BEIJING_TZ).isoformat(),
                "isDirectory": False
            })

    return array_of_files


def calculate_file_md5(file_path: str) -> str:
    """计算文件的MD5值"""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def calculate_dir_md5(dir_name: str) -> str:
    """计算目录的MD5值，使用目录名的哈希值"""
    return hashlib.md5(dir_name.encode('utf-8')).hexdigest()


def load_previous_manifest(file_path: str) -> Dict[str, Any]:
    """加载上一次的清单文件"""
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"files": {}}


def load_changes(changes_path: str) -> List[Dict[str, Any]]:
    """加载变更历史记录"""
    if os.path.exists(changes_path):
        with open(changes_path, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []


def process_file_info(file_path: str, base_path: str) -> Dict[str, Any]:
    """处理单个文件信息"""
    stat = os.stat(file_path)
    file_md5 = calculate_file_md5(file_path)
    relative_path = os.path.relpath(file_path, base_path)

    return {
        "path": relative_path,
        "size": stat.st_size,
        "modifiedTime": datetime.datetime.fromtimestamp(stat.st_mtime, BEIJING_TZ).isoformat(),
        "isDirectory": False,
        "md5": file_md5
    }


def process_directory_info(dir_path: str, base_path: str) -> Dict[str, Any]:
    """处理目录信息"""
    stat = os.stat(dir_path)
    relative_path = os.path.relpath(dir_path, base_path)

    return {
        "path": relative_path,
        "size": 0,
        "modifiedTime": datetime.datetime.fromtimestamp(stat.st_mtime, BEIJING_TZ).isoformat(),
        "isDirectory": True,
        "md5": calculate_dir_md5(relative_path)
    }


def collect_file_changes(new_files: Dict[str, Dict], previous_files: Dict[str, str]) -> Dict[str, List]:
    """收集文件变更信息"""
    changes = {
        "added": [],
        "removed": [],
        "modified": []
    }

    # 创建反向映射表：路径->MD5
    prev_path_to_md5 = {}
    for md5, path in previous_files.items():
        prev_path_to_md5[path] = md5

    # 检查新增和修改的文件
    for path, info in new_files.items():
        if path in prev_path_to_md5:
            # 文件已存在，检查MD5是否变化
            old_md5 = prev_path_to_md5[path]
            new_md5 = info["md5"]
            if old_md5 != new_md5:
                changes["modified"].append({
                    "filename": path,
                    "old_md5": old_md5,
                    "new_md5": new_md5
                })
        else:
            # 新增文件
            changes["added"].append({"filename": path, "md5": info["md5"]})

    # 检查删除的文件
    for path, md5 in prev_path_to_md5.items():
        if path not in new_files:
            changes["removed"].append({
                "filename": path,
                "last_md5": md5
            })

    return changes


def clean_unused_md5_files(md5s_dir: str, current_md5s: set) -> None:
    """清理不再使用的MD5文件"""
    for file_name in os.listdir(md5s_dir):
        if file_name.endswith('.json'):
            md5 = file_name[:-5]  # 移除.json后缀
            if md5 not in current_md5s:
                try:
                    os.remove(os.path.join(md5s_dir, file_name))
                except OSError as e:
                    print(f"Warning: Failed to remove unused MD5 file {file_name}: {e}")


def generate_manifest() -> None:
    try:
        # 获取路径
        script_dir = os.path.dirname(os.path.abspath(__file__))
        chip_docs_path = os.path.normpath(os.path.join(script_dir, "..", ))
        output_path = os.path.normpath(os.path.join(script_dir, "..", ".data", "file-manifest.json"))
        md5s_dir = os.path.normpath(os.path.join(script_dir, "..", ".data", "md5s"))
        changes_path = os.path.normpath(os.path.join(script_dir, "..", ".data", "changes.json"))

        # 确保输出目录存在
        for dir_path in [os.path.dirname(output_path), md5s_dir]:
            if not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)

        # 获取所有文件
        print(f"Scanning directory: {chip_docs_path}")
        print(f"Output will be written to: {output_path}")

        # 处理文件信息
        files_info = {}
        manifest_dict = {}
        current_md5s = set()  # 跟踪当前所有的MD5值

        for item in os.listdir(chip_docs_path):
            # 忽略以点开头的文件和目录
            if item.startswith('.'):
                continue

            full_path = os.path.join(chip_docs_path, item)

            if os.path.isdir(full_path):
                dir_info = process_directory_info(full_path, chip_docs_path)
                files_info[dir_info["path"]] = dir_info

                # 处理子目录
                for root, dirs, filenames in os.walk(full_path):
                    # 忽略以点开头的目录
                    dirs[:] = [d for d in dirs if not d.startswith('.')]

                    for filename in filenames:
                        # 忽略以点开头的文件
                        if filename.startswith('.'):
                            continue

                        file_path = os.path.join(root, filename)
                        file_info = process_file_info(file_path, chip_docs_path)
                        files_info[file_info["path"]] = file_info

                        # 使用相对路径作为键值对映射
                        rel_path = file_info["path"]
                        manifest_dict[file_info["md5"]] = rel_path

                        current_md5s.add(file_info["md5"])
            else:
                # 忽略以点开头的文件
                if item.startswith('.'):
                    continue

                file_info = process_file_info(full_path, chip_docs_path)
                files_info[file_info["path"]] = file_info

                # 使用相对路径作为键值对映射
                rel_path = file_info["path"]
                manifest_dict[file_info["md5"]] = rel_path

                current_md5s.add(file_info["md5"])

        # 清理不再使用的MD5文件
        clean_unused_md5_files(md5s_dir, current_md5s)

        # 生成MD5详细信息文件
        for file_info in files_info.values():
            if not file_info["isDirectory"]:
                detail_path = os.path.join(md5s_dir, f"{file_info['md5']}.json")
                with open(detail_path, "w", encoding="utf-8") as f:
                    json.dump(file_info, f, ensure_ascii=False)

        # 处理变更
        previous_manifest = load_previous_manifest(output_path)
        previous_files = previous_manifest.get("files", {})

        # 只包含非目录文件的信息
        file_infos_no_dir = {path: info for path, info in files_info.items() if not info["isDirectory"]}
        
        current_changes = {
            "timestamp": datetime.datetime.now(BEIJING_TZ).isoformat(),
            "changes": collect_file_changes(file_infos_no_dir, previous_files)
        }

        # 保存变更记录
        if any(current_changes["changes"].values()):
            changes_history = load_changes(changes_path)
            changes_history.append(current_changes)
            with open(changes_path, "w", encoding="utf-8") as f:
                json.dump(changes_history, f, ensure_ascii=False)

        # 保存新的manifest
        manifest = {
            "timestamp": datetime.datetime.now(BEIJING_TZ).isoformat(),
            "files": manifest_dict
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False)

        print(f"File manifest generated at: {output_path}")
        print(f"MD5 details generated in: {md5s_dir}")
        print(f"Changes record generated at: {changes_path}")

    except Exception as error:
        print(f"Error generating file manifest: {error}")
        raise

if __name__ == "__main__":
    try:
        generate_manifest()
    except Exception as error:
        print(f"Error: {error}")
        exit(1)
