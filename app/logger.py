import os
import logging
from logging.handlers import RotatingFileHandler
from config import base_log_path


logger = logging.getLogger('quart_app')
logger.setLevel(logging.INFO)

# Set log file name
log_file_name = "app.log"
log_file_path = os.path.join(base_log_path, log_file_name)

# Create log directory if it doesn't exist
os.makedirs(base_log_path, exist_ok=True)

# Configure console handler
c_handler = logging.StreamHandler()
# Configure file handler with log rotation
f_handler = RotatingFileHandler(log_file_path, maxBytes=10 ** 6, backupCount=5)

# Set format for console and file handler
c_format = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
f_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

# Apply format to console and file handler
c_handler.setFormatter(c_format)
f_handler.setFormatter(f_format)

# Add console and file handler to logger
logger.addHandler(c_handler)
logger.addHandler(f_handler)


def get_logger():
    """
    Return the configured logger.
    """
    return logger
