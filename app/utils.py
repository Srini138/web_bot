from config import  guardrails_config
# import config
from app.models import init_models
from app.retriever import get_vector_store
from langchain.chains import RetrievalQA,ConversationalRetrievalChain
from langchain.memory import ConversationBufferWindowMemory
from langchain.prompts import PromptTemplate
from nemoguardrails import RailsConfig
from app.logger import get_logger

# Gets logger
logger = get_logger()


def load_config():
    """
    Load configuration for Rails from provided colang and yaml content.
    """
    try:
        return RailsConfig.from_path("app/"+guardrails_config)
    except Exception as e:
        logger.error(f"Error loading config: {str(e)}")
        raise


async def initialize_components():
    """
    Initialize embeddings and chat models, gets vector store, prompt and conversational chain
    required for the application.
    """
    try:
        config = load_config()
        llm, embeddings = await init_models()
        vector_store = await get_vector_store(embeddings)
        prompt_template = await create_prompt_template()
        qa_chain = create_qa_chain(llm, vector_store, prompt_template)
        return config, llm, qa_chain
    except Exception as e:
        logger.error(f"Error initializing components: {str(e)}")
        raise RuntimeError("Error initializing components") from e


async def create_prompt_template():
    """
        Creates and returns prompt template for generating prompts for QA model.
    """
    try:
        prompt_template = """You are a Schneider Assistant called SchneiderBot. Use the following context (delimited by <ctx></ctx>)  to answer the question. Return only the answer. Don't mention its source of Information in answer, If you can't find the answer
            just say I dont know, contact Schneider for further assistance.
            ------
            <ctx>
            {context}
            </ctx>
            ------
            {question}
            Answer:
            """

        return PromptTemplate(
            template=prompt_template, input_variables=["context", "question"]
        )
    except Exception as e:
        logger.error(f"Error creating prompt template: {str(e)}")
        raise


def create_qa_chain(llm, vector_store, prompt_template):
    """
        Creates and returns a Conversational retrieval chain for question answering.
    """
    try:
        rephrase_template =  """Given the following conversation and a follow up question, rephrase the follow up question to be a standalone question. If Follow Up Input doesn't need rephrasing strictly just repeat the question as it is.
        Chat History:
        {chat_history}
        Follow Up Input: {question}
        Standalone question:"""
        CONDENSE_QUESTION_PROMPT = PromptTemplate.from_template(rephrase_template)

        qa_chain = ConversationalRetrievalChain.from_llm(
            llm=llm,
            retriever=vector_store.as_retriever(),
            return_source_documents=True,
            memory=ConversationBufferWindowMemory(k=3,
                                                  memory_key="chat_history",
                                                  input_key="question", output_key='answer'),
            verbose=True,
            get_chat_history=lambda h: h,
            combine_docs_chain_kwargs={'prompt': prompt_template},
            condense_question_prompt=CONDENSE_QUESTION_PROMPT,
            return_generated_question=True,

        )
        return qa_chain

    except Exception as e:
        logger.error(f"Error creating Conversational RetrievalChain chain: {str(e)}")
        raise


