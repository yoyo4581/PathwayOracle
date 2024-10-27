import csv
from db import cQueryToServer
from KGInstance import KGCypher
import os

class kgSubgraph:
    def __init__(self, user_id, subject, instance_id, graphName, geneFile, pathFile):
        self.gene_Data = {}
        self.path_Data = {}
        self.user_id = user_id
        self.subject = subject
        self.instance_id = instance_id
        self.graphName = graphName
        self.geneFile = geneFile
        self.pathFile = pathFile

        self.dataLoad()
        self.kgMark()


    def dataLoad(self):
        print(os.getcwd())
        g_count = 0
        p_count = 0
        with open(self.geneFile, newline='') as csvfile:
            genereader = csv.reader(csvfile)
            for row in genereader:
                if g_count==0:
                    g_count = g_count + 1
                    continue
                self.gene_Data[row[1]] = {'teststat':row[0], 'pFdr':row[2]}
                g_count = g_count + 1
                
        with open(self.pathFile, newline='') as csvfile:
            pathreader = csv.reader(csvfile)
            for row in pathreader:
                if p_count==0:
                    p_count = p_count + 1
                    continue
                self.path_Data[row[0]] = {'pSize':row[1], 'pFdr':row[2], 'teststat':row[3]}
                p_count = p_count + 1
    
    #Load genes and pathways and identifies User node then creates links between User and genes and pathway nodes and function text nodes
    def kgMark(self):

        path_list = [ path for path, info in self.path_Data.items()]
        gene_list = [ gene for gene, info in self.gene_Data.items()]
        path_exp = [ info['teststat'] for path, info in self.path_Data.items()]
        path_sig = [ info['pFdr'] for path, info in self.path_Data.items()]
        path_size = [ info['pSize'] for path, info in self.path_Data.items()]
        gene_exp = [ info['teststat'] for gene, info in self.gene_Data.items()]
        gene_sig = [ info['pFdr'] for gene, info in self.gene_Data.items()]
        
        
        load_genes = cQueryToServer(query=KGCypher.linkGenes, parameters={"gene_list": gene_list, "subject":self.subject, 
                                                            "user_id":self.user_id, "instance_id":self.instance_id,
                                                            "gene_exp": gene_exp, "gene_sig":gene_sig})
        if load_genes[0]['linkCount']>0:
            print(f'Successfully linked genes: {load_genes[0]["linkCount"]}')
        else:
            print('Failed to link genes')

        
        load_paths = cQueryToServer(query=KGCypher.linkPaths, parameters={"path_list": path_list, "subject":self.subject, "user_id":self.user_id, 
                                                                   "instance_id":self.instance_id, "path_exp": path_exp, "path_sig":path_sig, 
                                                                   "path_size":path_size})
        if load_paths[0]['linkCount']>0:
            print(f'Successfully linked pathways: {load_paths[0]["linkCount"]}')
        else:
            print('Failed to link pathways')


        load_geneLinks = cQueryToServer(query=KGCypher.linkGeneRelationships, parameters={"path_list": path_list, "instance_id":self.instance_id})
        if load_geneLinks[0]['linkCount']>0:
            print(f'Successfully linked gene interactions: {load_geneLinks[0]["linkCount"]}')
        else:
            print('Failed to link gene interactions')


        load_pathLinks = cQueryToServer(query=KGCypher.linkPathRelationships, parameters={"path_list": path_list, "instance_id": self.instance_id})
        print(load_pathLinks)
        if load_pathLinks[0]['linkCount']>0:
            print(f'Successfully linked path associations: {load_pathLinks[0]["linkCount"]}')
        else:
            print('Failed to link path associations')
            
        
        load_funcLinks = cQueryToServer(query=KGCypher.linkFuncNodes, parameters={"instance_id":self.instance_id})
        print(load_funcLinks)
        if load_funcLinks[0]['linkCount']>0:
            print(f'Successfully linked function associations: {load_funcLinks[0]["linkCount"]}')
        else:
            print('Failed to link function associations')

        testy = """
        MATCH (i:Instance {instance_id: $instance_id})-[:LINKED_TO {instance_id:$instance_id}]->(n)
        With collect(n) as all_nodes
        UNWIND all_nodes as node
        MATCH (node)-[r]-(m)
        WHERE m in all_nodes AND $instance_id IN r.instance_ids
        RETURN node, r, m
        """
        load_subgraph = cQueryToServer(query=testy, parameters={"instance_id":self.instance_id})
        if load_subgraph and 'node' in load_subgraph[0] and load_subgraph[0]['node']:
            print('Marking KG Subgraph successful')
        else:
            print('Could not mark KG Subgraph')
            return