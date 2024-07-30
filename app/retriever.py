from langchain_community.vectorstores import Chroma
from app.logger import get_logger
from config import VECTOR_TABLE
# Gets logger
logger = get_logger()


async def get_vector_store(embeddings):
    """
    Retrieves the  vector table mentioned in env file from AlloyDB.
    """
    try:
        vector_store = Chroma(persist_directory="app/"+VECTOR_TABLE,embedding_function=embeddings)
        logger.info("Vector store has been retrieved!")
        return vector_store
    except Exception as e:
        logger.error(f"Error getting vector store: {str(e)}")
        raise RuntimeError("Error getting vector store") from e
