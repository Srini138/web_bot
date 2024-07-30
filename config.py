from quart.config import Config
from dotenv import load_dotenv, dotenv_values


config = Config(None)

load_dotenv()
config.from_mapping(dotenv_values())
base_log_path = config.get('LOG_DIR_PATH', './logs')
nvidia_api_key = config.get('NVIDIA_API_KEY')
VECTOR_TABLE = config.get('VECTOR_TABLE')
guardrails_config = config.get("GUARDRAILS_CONFIG")
sitemap_url = config.get("SITEMAP_URL")