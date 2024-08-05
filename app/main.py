from quart import request, jsonify, render_template, Quart
from quart_cors import cors
from app.utils import initialize_components
from app.rails import MyRails
import nest_asyncio
from nemoguardrails.streaming import StreamingHandler
nest_asyncio.apply()

# Configure logger
from app.logger import get_logger
logger = get_logger()

app = Quart(__name__)

# Enable CORS for all routes
cors(app)
streaming_handler = StreamingHandler()

# Declare app_llm and qa_chain as global variables
app_llm = None
qa_chain = None

async def startup():
    """
    Initialize components required for the application.
    """
    global app_llm, qa_chain
    try:
        config, llm, qa_chain = await initialize_components()
        app_llm = MyRails(config, llm=llm)
        app_llm.register_action(qa_chain, name="qa_chain")
        logger.info("LLM Rails configured successfully")
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")

def generate_response(user_message):
    """
    Generate response for the given user message using LLMRails.
    """
    global app_llm
    if app_llm is None:
        logger.error("app_llm is not initialized")
        return "Error: System not ready. Please try again later.", []

    try:
        bot_message = app_llm.generate(messages=[{"role": "user", "content": user_message}])
        try:
            source = [i.metadata['source'] for i in bot_message['source_documents']]
        except:
            source = []
        return bot_message['content'], source
    except Exception as e:
        logger.error(f"Error in generating response: {str(e)}")
        return "Error processing your request.", []

@app.route("/")
async def main():
    """
    Render the main HTML page.
    """
    return await render_template("./base.html")

@app.route('/get_response', methods=['POST'])
async def bot_endpoint():
    """
    Endpoint to receive user messages and return bot responses.
    """
    try:
        input_prompt = await request.json
        if 'message' in input_prompt:
            bot_message, source_docs = generate_response(input_prompt['message'])
            logger.info("Response successfully generated.")
            return jsonify({"response": bot_message, "source_docs": source_docs})
        else:
            logger.error("Message not found in request")
            return jsonify({"response": "Message not found"})
    except Exception:
        logger.exception("Failed to fetch or generate response")
        return jsonify({"response": "Failed to process request"})

if __name__ == "__main__":
    # Run the startup initialization
    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_until_complete(startup())
    
    # Run the Quart app in debug mode
    app.run(host="0.0.0.0", port=5000, debug=True)
