from langchain_nvidia_ai_endpoints import ChatNVIDIA, NVIDIAEmbeddings
from app.logger import get_logger
from config import nvidia_api_key

# Gets logger
logger = get_logger()



async def init_models():
    """
    Initializes and returns NVIDIA ChatNVIDIA and NVIDIAEmbeddings models.
    """
    try:

        if not nvidia_api_key:
            logger.error("NVIDIA_API_KEY environment variable is not set.")
            raise ValueError("NVIDIA_API_KEY environment variable is not set.")

        llm = ChatNVIDIA(model="ai-llama2-70b",temperature=0)
        embeddings = NVIDIAEmbeddings(model="ai-embed-qa-4")
        logger.info("LLM and embedding models has been initialised")
        return llm, embeddings

    except Exception as e:
        logger.error(f"Error initializing models: {str(e)}")
        raise
