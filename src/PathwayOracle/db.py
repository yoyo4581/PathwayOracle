import os
from pprint import pprint
from langchain_community.graphs import Neo4jGraph
from langchain_community.chat_models import ChatOpenAI


from dotenv import load_dotenv
import os

from langchain_openai import ChatOpenAI


import requests
import time
from dotenv import load_dotenv

from flask import jsonify
import requests
from requests.exceptions import JSONDecodeError


load_dotenv()

out_server = 'https://azureflask-po.azurewebsites.net'
#in_server = 'http://127.0.0.1:5000'

llm = None

def VMServer_Initialize(action):
    if action=='status':
        try:
            #Sending GET request to the server for VM current status
            response = requests.get(out_server + '/status-vm')
            print('VM Response Status:', response.text)
            return True
        except requests.exceptions.RequestException as e:
            # Handle exceptions during the request
            print(f"Error calling the API: {e}")
            return False
    elif action=='start':
        try:
            #Sending GET request to the server for VM start
            response = requests.get(out_server + '/start-vm')
            print('VM Response Start:', response.text)
            return True
        except requests.exceptions.RequestException as e:
            print(f"Error calling the API: {e}")
            return False

def queryToServer(query):
    time.sleep(3)  # Delay for throttling purposes
    
    try:
        # Sending GET request to the server
        response = requests.get(out_server + '/query', params={'query': query})
        #print('Response Status:', response.status_code)

        if response.status_code == 200:
            try:
                # Attempt to decode the response as JSON
                return response.json()
            except JSONDecodeError:
                print("Error decoding JSON, raw response:", repr(response.text))
                return None  # Return None if JSON decoding fails
        else:
            # Handle non-200 status codes
            print(f"Error: Received status code {response.status_code}")
            print("Raw response:", repr(response.text))
            return None
    except requests.exceptions.RequestException as e:
        # Handle any network-related errors
        print(f"Request failed: {e}")
        return None

def cQueryToServer(query, parameters):
    time.sleep(3)  # Adding delay for rate-limiting or throttling purposes
    data = {'query': query, 'params': parameters}
    
    try:
        response = requests.post(out_server + '/cQuery', json=data)
        #print('Response Status:', response.status_code)

        if response.status_code == 200:
            try:
                # Attempt to decode the response as JSON
                return response.json()
            except JSONDecodeError:
                print("Error decoding JSON, raw response:", repr(response.text))
                return None  # Avoid returning an invalid JSON response
        else:
            # Handle non-200 status codes gracefully
            print(f"Error: Received status code {response.status_code}")
            print("Raw response:", repr(response.text))
            return None
    except requests.exceptions.RequestException as e:
        # Handle any connection or request errors
        print(f"Request failed: {e}")
        return None


OPENAI_MODEL = 'gpt-4o-mini'
# OPENAI_FINETUNED_MODEL = "ft:gpt-4o-mini-2024-07-18:personal:breast-cancer-4:AKui83Dw"


try:
    print("Attempting connection with LLM ChatOpenAi")
    chat_llm = ChatOpenAI(openai_api_key = os.environ['OPENAI_API_KEY'], temperature=0.2, model=OPENAI_MODEL, streaming=True)
    llm = ChatOpenAI(
        openai_api_key = os.environ['OPENAI_API_KEY'] ,
        model = OPENAI_MODEL,
        temperature=0.2
    )
except Exception as e:
    print(f"An error occurred: {e}")
else:
    print('Connection successful')



__all__ = ['chat_llm', 'llm']