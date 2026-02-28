"""翻译校验工具 - 程序入口。"""

import sys
import os
import json
import logging

# 路径适配：打包后使用 exe 所在目录，开发时使用项目目录
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            os.path.join(BASE_DIR, "translation_checker.log"),
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

DEFAULT_CONFIG = {
    "provider": "自定义",
    "base_url": "",
    "api_key": "",
    "model": "",
    "request_interval": 1.0,
    "batch_mode": False,
    "batch_size": 5,
    "custom_prompts": {},
}


def load_config():
    """加载配置文件，不存在则创建默认配置。"""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)
            # 确保所有默认字段存在
            for key, value in DEFAULT_CONFIG.items():
                if key not in config:
                    config[key] = value
            return config
        except Exception as e:
            logger.warning(f"加载配置失败，使用默认配置: {e}")

    # 写入默认配置
    config = DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"写入默认配置失败: {e}")
    return config


def main():
    logger.info(f"程序启动，基础目录: {BASE_DIR}")

    config = load_config()

    from gui.app import MainApp

    app = MainApp(config=config, config_path=CONFIG_PATH, base_dir=BASE_DIR)
    app.mainloop()


if __name__ == "__main__":
    main()
