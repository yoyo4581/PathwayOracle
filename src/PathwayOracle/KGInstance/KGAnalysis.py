from KGInstance import KGCypher
from db import cQueryToServer, queryToServer
import numpy as np
from collections import Counter
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import KMeans
import torch
from transformers import BertTokenizer, BertModel


class kgAnalysis:
    def __init__(self, graphName=None, instance_id=None, recovery=False):
        self.graphName = graphName
        self.instance_id = instance_id

        self.wcc_res = self.kgAnalysis()
        self.recovery = recovery

        if not self.recovery:
            self.ref_Abstracts = self.primeAbstracts()
            self.tokenizer = BertTokenizer.from_pretrained('dmis-lab/biobert-base-cased-v1.2')
            self.model = BertModel.from_pretrained('dmis-lab/biobert-base-cased-v1.2')

    # Now conduct on the marked Subgraph kgAnalysis. This includes:
    #1. Conducting WCC analysis. Identifying components. Storing summary statistics in the object.
    def kgAnalysis(self):

        print("Conducting WCC analysis: Creating a graph projection")
        #Create a graph projection
        graph_create = cQueryToServer(query=KGCypher.graph_proj, parameters={"instance_id":self.instance_id, "graphName":self.graphName})
        print("graph specs", graph_create)

        #Results are names of genes or Pathways and the component they belong to.
        wcc_res = cQueryToServer(query=KGCypher.wcc_analysis, parameters={"graphName":self.graphName})
        
        #4. Identify summary statistics. Namely the componentNumber is useful which is 11.
        
        summ_res = cQueryToServer(query=KGCypher.wcc_summ, parameters={"graphName":self.graphName})
        print('Number of components identified:',summ_res[0]['componentCount'])

        #5. Drop the graph from memory:
        try:
            drop_graph = """
            CALL gds.graph.drop($graphName)
            """
            graph_dropped = cQueryToServer(query=drop_graph, parameters={"graphName":self.graphName})
        except:
            print("WCC Graph not found")
        else:
            print("WCC Analysis Completed")

        # Format wcc results
        def wcc_stats(dict_array):
            compoSum = {}
            prev_group = None
            
            for entry in dict_array:
                if entry['componentId']!=prev_group:
                    prev_group = entry['componentId']
                    compoSum[entry['componentId']]=0
                    
                compoSum[entry['componentId']] += 1

            for compo_key in compoSum.keys():
                print('Component ', compo_key, 'has', compoSum[compo_key], 'members')
                
            return compoSum
        
        def reformat_wcc(wcc_res):
            reformatted_WCC = {}
            for entry in wcc_res:
                reformatted_WCC[entry['componentId']] = []

            for entry in wcc_res:
                reformatted_WCC[entry['componentId']].append(entry['name'])

            return reformatted_WCC

        stat_res = wcc_stats(wcc_res)
        print(stat_res)

        wcc_res_formatted = reformat_wcc(wcc_res)

        return wcc_res_formatted
    
    
    
    def generateEmbeds(self, text):
        inputs = self.tokenizer(text, return_tensors='pt', truncation=False, padding=True)
        with torch.no_grad():
            question_outputs = self.model(**inputs)
    
        question_embedding = torch.mean(question_outputs.last_hidden_state, dim=1).squeeze().numpy()
    
        return question_embedding


    def score(self, sentences, question):
        # Ensure sentences is a 2D array
        similarities = cosine_similarity(sentences, question.reshape(1, -1))
        ranked_similarities = np.sort(similarities.flatten())[::-1]
        return similarities, ranked_similarities
    
        
        