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

import requests
import json
import time

out_server = 'https://azureflask-po.azurewebsites.net'
in_server = 'http://127.0.0.1:5000'




llm = None

def queryToServer(query):
    print(query)
    time.sleep(3)
    response = requests.get(out_server+'/query', params={'query': query})
    print(response.status_code)
    return response.json()

def cQueryToServer(query, parameters):
    print(query, parameters)
    time.sleep(3)
    data = {'query':query, 'params':parameters}
    response = requests.post(out_server+'/cQuery', json=data)
    print('Response Status', response.status_code)
    return response.json()

def connect_to_LLM(llm_key, llm_opt):
    global llm
    try:
        print("Attempting connection with LLM ChatOpenAi")
        llm = ChatOpenAI(
            openai_api_key = llm_key,
            model = llm_opt,
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
    
