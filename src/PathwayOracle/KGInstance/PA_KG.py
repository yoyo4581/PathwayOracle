from transformers import BertTokenizer, BertModel
from sklearn.metrics.pairwise import cosine_similarity
from collections import Counter
import numpy as np
from sklearn.cluster import KMeans
from langchain.docstore.document import Document
from collections import defaultdict
from .KGInstance import KG_InstanceFind
from .KGMark import kgSubgraph
from .KGAnalysis import kgAnalysis
from .KGRetrieval import AgentRetrieval
from ..AgentFiles.Agent import agent_executor
from typing import List, Tuple
from ..LLM_Summarization.LLM_Sum import LLM_Summ
from ..db import VMServer_Initialize



class PA_KG:

    def __init__(self, email= None, user= None, subject=None):
        
        self.recoveryMode = False
        # Regardless each facade has an object Instance Manager

        #The first thing we do is check if the VM is on, and if it is, then configure instance
        self.VM_Status = self.VM_Communicate()
        # This first identifies the user and if the user is not found it creates one.
        self.kgObj = KG_InstanceFind(email=email, user=user, subject=subject)

    def VM_Communicate(self):
        # The first thing we will do is get the VM Status
        response = VMServer_Initialize(action='status')
        if response:
            return response
        #The status is False (Not initialized)
        else:
            #It can still fail, but if it does, then the user would be alerted that the api isnt working
            response = VMServer_Initialize(action='start')
            return response
        
    def fromInstance(self, instance_id = None):
        self.recoveryMode = True
        self.kgObj.fromInstance(instance=instance_id)
        self.analysis = kgAnalysis(instance_id= self.kgObj.instance_id, graphName= self.kgObj.graphName, recovery=self.recoveryMode)

    def newInstance(self):
        self.kgObj.newInstance()

    def removeInstance(self, instanceList):
        self.kgObj.removeInstances(instanceList=instanceList)

    def showInstance(self):
        instances = self.kgObj.showInstances()
        return instances
    
    def to_Doc(self, folder):
        import os
        preString = os.getcwd()
        folderPath = os.path.join(preString, folder)

        # Ensure 'summaryFiles' directory exists
        if not os.path.exists(folderPath):
            os.makedirs(folderPath)

        print('Writing txt files to directory', folderPath)
        
        for compoKey, subcompos in self.summedDocs.items():
            for subcompoKey, final_summ in subcompos.items():
                retain_val = final_summ['retain']
                if retain_val:
                    fileString = os.path.join(folderPath, f'Component_{str(compoKey)}_Sub_{str(subcompoKey)}.txt')
                    with open(fileString, 'w', encoding='utf-8') as f:
                        f.write(str(final_summ['final_summary']))
        


    async def generateSummaries(self, folder_name, to_write=True):

        summedDocs = defaultdict(lambda: defaultdict(dict))

        for compoKey, subcompos in self.SummedObj.groupedDocuments.items():
            for subcompoKey, docs in subcompos.items():
                print(f'Working on component key: {compoKey}, subcomponent key: {subcompoKey}')
                print(' '.join([ doc.metadata['Name'] for doc in docs]))

                if len(docs)>1:
                    async for step in self.SummedObj.app_big.astream(
                        {"contents": docs},
                        {"recursion_limit": 15},
                    ):
                        print(list(step.keys()))
                    
                    summedDocs[compoKey][subcompoKey] = step['evaluate_final_summary']
                else:
                    async for step in self.SummedObj.app_small.astream(
                        {"contents": docs},
                        {"recursion_limit": 15},
                    ):
                        print(list(step.keys()))
                    if 'generate_final_summary' in step:
                        summedDocs[compoKey][subcompoKey] = step['generate_final_summary']
                    else:
                        reformattedDict = {'final_summary': step['evaluate_summary']['content'],
                                           'retain': step['evaluate_summary']['retain']}
                        summedDocs[compoKey][subcompoKey] = reformattedDict
        
        self.summedDocs = summedDocs
        if to_write:
            self.to_Doc(folder=folder_name)

        return summedDocs    

    def processAll(self, geneFile, pathFile, token_max=1000):
        if self.recoveryMode:
            print("Do not reprocess data from pre-existing instance. Use fromInstance method with instance_id.")
            return
        
        self.subgraph = kgSubgraph(user_id = self.kgObj.user_id, subject = self.kgObj.subject, instance_id = self.kgObj.instance_id, graphName=self.kgObj.graphName, geneFile=geneFile, pathFile=pathFile)

        self.analysis = kgAnalysis(instance_id= self.kgObj.instance_id, graphName= self.kgObj.graphName, recovery=self.recoveryMode)

        self.agentRet = AgentRetrieval(subject=self.kgObj.subject, wcc_res=self.analysis.wcc_res, instance_id= self.kgObj.instance_id)


    def Retrieval(self, components_select: dict[str, list]=None):
        self.retrieved_Docs = self.agentRet.agentCommunicate(component_Select=components_select)

    def Summarize(self, components_select: dict[str, list]=None, token_max=1000):
        self.SummedObj = LLM_Summ(subject= self.kgObj.subject, components_selection=components_select, groupedDocuments=self.retrieved_Docs, token_max=token_max)

        
# Idealy Marking and Analysis are always performed        
# Retrieval is partially performed.    
        
        
     
