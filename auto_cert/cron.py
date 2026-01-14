"""定时任务调度器，用于自动执行证书续订和SLB证书更新。"""

import logging
import signal
import sys
import time
from typing import Optional

import schedule

from .config import Config
from .renew_cert import main as renew_cert_main
from .update_slb_cert import main as update_slb_cert_main

# 设置日志
logger = logging.getLogger(__name__)


class CronScheduler:
    """定时任务调度器"""

    def __init__(self, interval_hours: Optional[int] = None):
        """
        初始化调度器

        Args:
            interval_hours: 执行间隔（小时），如果为None则使用Config.CRON_INTERVAL_HOURS
        """
        if interval_hours is None:
            self.interval_hours = Config.CRON_INTERVAL_HOURS
        else:
            self.interval_hours = interval_hours

        # 验证间隔时间
        if self.interval_hours < 1:
            logger.warning(f"CRON_INTERVAL_HOURS不能小于1小时，使用默认值12小时")
            self.interval_hours = 12

        self.running = False
        self.scheduler = schedule.Scheduler()

        # 设置信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """处理退出信号"""
        logger.info(f"收到信号 {signum}，正在停止调度器...")
        self.running = False

    def _run_renew_cert(self) -> bool:
        """运行证书续订任务"""
        try:
            logger.info("开始执行证书续订检查...")

            # 验证配置
            errors = Config.validate()
            if errors:
                logger.error("配置错误:")
                for error in errors:
                    logger.error(f"  - {error}")
                return False

            # 导入并运行renew_cert的main函数
            # 注意：这里我们直接调用renew_cert_main()，它会处理所有逻辑
            # 包括检查是否需要续订，以及执行续订操作
            logger.info("调用证书续订模块...")

            # 由于renew_cert.main()使用sys.exit()，我们需要捕获SystemExit
            try:
                renew_cert_main()
                logger.info("证书续订任务执行完成")
                return True
            except SystemExit as e:
                # renew_cert.main()在成功时调用sys.exit(0)，失败时调用sys.exit(1)
                if e.code == 0:
                    logger.info("证书续订成功或无需续订")
                    return True
                else:
                    logger.error("证书续订失败")
                    return False

        except Exception as e:
            logger.error(f"执行证书续订时发生错误: {e}")
            return False

    def _run_update_slb_cert(self) -> bool:
        """运行SLB证书更新任务"""
        try:
            logger.info("开始执行SLB证书更新...")

            # 验证配置
            errors = Config.validate()
            if errors:
                logger.error("配置错误:")
                for error in errors:
                    logger.error(f"  - {error}")
                return False

            # 检查是否配置了SLB
            if not Config.SLB_INSTANCE_ID or not Config.SLB_LISTENER_ID:
                logger.info("未配置SLB，跳过SLB证书更新")
                return True

            logger.info("调用SLB证书更新模块...")

            # 由于update_slb_cert.main()使用sys.exit()，我们需要捕获SystemExit
            try:
                update_slb_cert_main()
                logger.info("SLB证书更新任务执行完成")
                return True
            except SystemExit as e:
                if e.code == 0:
                    logger.info("SLB证书更新成功")
                    return True
                else:
                    logger.error("SLB证书更新失败")
                    return False

        except Exception as e:
            logger.error(f"执行SLB证书更新时发生错误: {e}")
            return False

    def _run_all_tasks(self):
        """执行所有定时任务"""
        logger.info(f"=== 开始执行定时任务（每{self.interval_hours}小时）===")

        # 执行证书续订
        renew_success = self._run_renew_cert()

        # 如果证书续订成功，执行SLB证书更新
        if renew_success:
            self._run_update_slb_cert()
        else:
            logger.warning("证书续订失败，跳过SLB证书更新")

        logger.info(f"=== 定时任务执行完成，{self.interval_hours}小时后再次执行 ===")

    def start(self):
        """启动调度器"""
        logger.info(f"启动定时任务调度器，每{self.interval_hours}小时执行一次")
        logger.info("任务包括：证书续订检查 + SLB证书更新")
        logger.info("按 Ctrl+C 停止")

        # 安排任务
        self.scheduler.every(self.interval_hours).hours.do(self._run_all_tasks)

        # 立即执行一次
        logger.info("立即执行第一次任务...")
        self._run_all_tasks()

        self.running = True

        # 主循环
        while self.running:
            try:
                self.scheduler.run_pending()
                time.sleep(60)  # 每分钟检查一次
            except KeyboardInterrupt:
                logger.info("收到键盘中断，停止调度器...")
                self.running = False
            except Exception as e:
                logger.error(f"调度器运行错误: {e}")
                # 继续运行，不退出

    def stop(self):
        """停止调度器"""
        logger.info("停止调度器...")
        self.running = False


def main():
    """主函数"""
    # 设置日志格式
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger.info("启动证书自动管理调度器")

    # 创建并启动调度器（使用Config.CRON_INTERVAL_HOURS）
    scheduler = CronScheduler()
    logger.info(f"调度间隔: 每{Config.CRON_INTERVAL_HOURS}小时执行一次")
    scheduler.start()


if __name__ == "__main__":
    main()