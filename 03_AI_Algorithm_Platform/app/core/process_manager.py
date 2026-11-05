import asyncio
from multiprocessing import get_context

class ProcessManager:
    """线程安全的多进程资源管理器"""

    def __init__(self):
        self.running = False
        self._manager = None
        self.global_queue = None
        self.task_map = {}
        self.lock = asyncio.Lock()
        self.ctx = get_context('spawn')

    def initialize(self):
        """显式初始化方法"""
        if not self._manager:
            self.running = True
            self._manager = self.ctx.Manager()
            self.global_queue = self._manager.Queue()

    def shutdown(self):
        """安全关闭方法"""
        if self._manager:
            self.running = False
            self._manager.shutdown()
            self._manager = None