from pathlib import Path

from app.config import StorageConfig
from app.services.storage.base import StorageService

# 本地存储服务实现
class LocalStorageService(StorageService):
    # 初始化
    def __init__(self, config: StorageConfig):
        # 根目录
        self.base_dir = Path(config.local_dir)
        # 自动创建目录
        self.base_dir.mkdir(parents=True, exist_ok=True)

    # 映射文件路径
    def _path_for_key(self, key: str) -> Path:
        return self.base_dir / key
    
    # 保存文件
    def save(self, data: bytes, key: str) -> str:
        path = self._path_for_key(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key
    
    # 加载文件
    def load(self, key: str) -> bytes:
        return self._path_for_key(key).read_bytes()
    
    # 删除文件
    def delete(self, key: str) -> None:
        self._path_for_key(key).unlink()
    
    # 获取文件绝对路径
    def get_absolute_path(self, key: str) -> str:
        return str(self._path_for_key(key).resolve())
