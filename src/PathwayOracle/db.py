# db.py

from langchain_community.graphs import Neo4jGraph
from dotenv import load_dotenv
import os

from langchain_openai import ChatOpenAI
from langchain_openai import OpenAIEmbeddings
from langchain.prompts.prompt import PromptTemplate
from langchain_community.vectorstores.neo4j_vector import Neo4jVector

from langchain.prompts.prompt import PromptTemplate
from langchain.chains import GraphCypherQAChain

load_dotenv()

kg_user = os.getenv("USER")
kg_pswd = os.getenv("PASSWORD")
kg_url = os.getenv("NEO4J_URL")
llm_key = os.getenv("OPEN_API_KEY")
OPENAI_MODEL = "gpt-3.5-turbo"

graph = None
llm = None

def connect_to_db():
    global graph
    try:
        print("Attempting connection with graph database")
        graph = Neo4jGraph(
            url=kg_url,
            username=kg_user,
            password=kg_pswd
        )
    except:
        print("Server is down")
    else:
        print("Connection successful")
        return graph

def connect_to_LLM(llm_opt = llm_key):
    global llm
    try:
        print("Attempting connection with LLM ChatOpenAi")
        llm = ChatOpenAI(
            openai_api_key = llm_opt,
            model = OPENAI_MODEL,
            temperature=0.0
        )

        embeddings= OpenAIEmbeddings(
            openai_api_key=llm_opt
        )
    except:
        print("Incorrect API key")
    else:
        print('Connection successful')
        return llm
    
