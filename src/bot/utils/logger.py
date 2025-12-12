import logging
from logging.handlers import RotatingFileHandler
import os

def setup_logger(name: str = 'k17_bot') -> logging.Logger:    
    # Create logs directory if it doesn't exist
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # Configure root logger to capture all logs
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Create logger for the bot
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Create formatters
    file_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_formatter = logging.Formatter(
        '%(levelname)-8s | %(message)s'
    )
    
    # File handler (rotating)
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, 'bot.log'),
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(file_formatter)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    
    # Add handlers to root logger so all loggers inherit them
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    return logger
