from .db import queryToServer, cQueryToServer
import subprocess
import csv
import random
import os

class PA_KG:
    
    gene_Data = {}
    path_Data = {}


    def check_file_exists(self, file_path):
        exists = os.path.exists(file_path)
        if exists:
            print(f"The file {file_path} exists.")
        else:
            print(f"The file {file_path} does not exist.")

    def expID_retrieve(self):
        return self.exp_id

    def __init__(self, pathGene, pathGroup, subject):
        self.subject = subject
        self.pathGene = pathGene
        self.pathGroup = pathGroup

        self.check_file_exists(self.pathGene)
        self.check_file_exists(self.pathGroup)

        exp_id = subject.replace(" ","_")
        random_number = random.randint(0, 999)
        random_string = f"{random_number:03}"
        exp_id += '_'+random_string

        self.exp_id = exp_id
        self.clone_relation = exp_id+'_rel'
        self.common_text = exp_id+'_text'
        self.textIndex_label = self.common_text+'Embed'
        self.scoreString = self.common_text+'Score'

        self.wcc_res = None
 
    def pathwayAnalysis(self):
        script_dir = os.path.dirname(os.path.realpath(__file__))

        # Construct the absolute path of netGSA.R
        netgsa_path = os.path.join(script_dir, 'netGSA.R')

        #conduct PA using netGSA and edges file
        command = ["Rscript", netgsa_path, self.pathGene, self.pathGroup, script_dir]

        subprocess.run(command)


    def dataLoad(self):
        g_count = 0
        p_count = 0
        with open('./gene_results.csv', newline='') as csvfile:
            genereader = csv.reader(csvfile)
            for row in genereader:
                if g_count==0:
                    g_count = g_count + 1
                    continue
                self.gene_Data[row[1]] = {'teststat':row[0], 'pFdr':row[2]}
                g_count = g_count + 1
                
        with open('./pathway_results.csv', newline='') as csvfile:
            pathreader = csv.reader(csvfile)
            for row in pathreader:
                if p_count==0:
                    p_count = p_count + 1
                    continue
                self.path_Data[row[0]] = {'pSize':row[1], 'pFdr':row[2], 'teststat':row[3]}
                p_count = p_count + 1


    # def checkVector_Index(self):
    #     textCheck = f"""
    #     SHOW index
    #     """

    #     textChecker = queryToServer(textCheck)
    #     found_idx = False
    #     for index in textChecker:
    #         if index['name'] == self.textIndex_label:
    #             found_idx = True

    #     if found_idx:
    #         print('Vector Index created successfully')
    #     else:
    #         print('Error Vector Index not created')


    def scoreText(self):
        print('Starting graph-enhanced semantic scoring of text embeds')
        #Add text tag
        text_tag= f"""
        MATCH (n:TextNode:{self.exp_id})
        SET n:{self.common_text}
        RETURN n
        """

        text_res = queryToServer(query=text_tag)

        print('Creating a vector index')
        indexConfig = {
            'vector.dimensions': 1536,
            'vector.similarity_function': "'cosine'"
        }

        configItems = ", ".join(f"`{k}`: {v}" for k, v in indexConfig.items())
        options = f"{{indexConfig: {{{configItems}}}}}"

        textVec_index = f"""
        CREATE VECTOR INDEX `{self.textIndex_label}`
        FOR (n:{self.common_text}) ON (n.embedding)
        OPTIONS {options}
        """

        textVec = queryToServer(textVec_index)

        score_call_linked = f"""
        MATCH (t1:{self.common_text})<-[:CONTAINS]-(g:Genes:{self.exp_id})
        WITH g, collect(t1) as subject_text
        UNWIND subject_text as sub_T
        MATCH (sub_T)<-[:CONTAINS]-(g:Genes:{self.exp_id})-[r]-(g2:Genes:{self.exp_id})-[:CONTAINS]->(obj_T:{self.common_text})
        WHERE g2 IS NOT NULL
        WITH sub_T, g, r, g2, obj_T, vector.similarity.cosine(sub_T.embedding,obj_T.embedding) as score
        ORDER BY score DESC
        WITH g, collect({{subject_node: sub_T, object_node: obj_T, score: score}}) as results
        WITH g, [res in results | res.score][..2] as top_two_scores, results
        UNWIND results as res
        WITH res
        WHERE res.score IN top_two_scores
        MATCH (n)
        WHERE id(n) IN [id(res.subject_node), id(res.object_node)]
        SET n:{self.scoreString}
        RETURN res.subject_node, res.object_node
        """

        linkScore = queryToServer(query=score_call_linked)
        if len(linkScore)>0:
            print('Linked Genes Text nodes have been scored')
        
        score_notlinked = f"""
        MATCH (t1:{self.common_text})<-[:CONTAINS]-(g:Genes:{self.exp_id})
        WHERE NOT (g)-[:{self.clone_relation}]-(:Genes:{self.exp_id})
        WITH g, collect(t1) as subject_Text
        UNWIND subject_Text as sub_T
        MATCH (sub_T)<-[:CONTAINS]-(g)-[:belongs_to]->(p:Pathway:{self.exp_id})<-[:belongs_to]-(g3:Genes:{self.exp_id})-[:CONTAINS]->(obj_T) 
        WITH g, sub_T, obj_T, g3, vector.similarity.cosine(sub_T.embedding,obj_T.embedding) as score
        ORDER BY score DESC
        WITH g, collect({{subject_node: sub_T, object_node: obj_T, score: score}}) as results
        WITH g, [res in results | res.score][..2] as top_two_scores, results
        UNWIND results as res
        WITH res
        WHERE res.score IN top_two_scores
        MATCH (n)
        WHERE id(n) IN [id(res.subject_node), id(res.object_node)]
        SET n:{self.scoreString}
        RETURN res.subject_node, res.object_node
        """
        notLinkScore = queryToServer(query=score_notlinked)
        if len(notLinkScore)>0:
            print('Non-linked Genes Text nodes have been scored')
        


    def kgAnalysis(self):
        clone_rel = f"""
        MATCH (n:{self.exp_id})-[r]->(m:{self.exp_id})
        WHERE '{self.exp_id}' IN r.tags
        MERGE (n)-[r2:{self.clone_relation}]->(m)
        SET r2 = r
        RETURN n, r2, m
        """

        clone_results = cQueryToServer(query=clone_rel,
                                         parameters={"clone_relation":self.clone_relation})
        
        test2 = f"""
        MATCH ()-[r:{self.clone_relation}]->() RETURN count(r)
        """

        test2_res = queryToServer(query=test2)

        if int(test2_res[0]['count(r)'])>0:
            print('Successfully created temporary cloned relationships')

        print("Conducting WCC analysis")
        #Create a graph projection
        graph_proj = """
        CALL gds.graph.project(
            'myGraph',
            $exp_id,
            $clone_relation
        )
        YIELD
        graphName AS graph, nodeProjection, nodeCount AS nodes, relationshipProjection, relationshipCount AS rels
        """
        graph_create = cQueryToServer(query=graph_proj, parameters={"exp_id":self.exp_id, "clone_relation":self.clone_relation})

        wcc_analysis = """
        CALL gds.wcc.stream('myGraph')
        YIELD nodeId, componentId
        WHERE gds.util.asNode(nodeId).name IS NOT NULL
        RETURN gds.util.asNode(nodeId).name AS name, componentId
        ORDER BY componentId, name
        """
        #Results are names of genes or Pathways and the component they belong to.
        wcc_res = queryToServer(query=wcc_analysis)
        
        #4. Identify summary statistics. Namely the componentNumber is useful which is 11.

        wcc_summ = """
        CALL gds.wcc.stats('myGraph')
        YIELD componentCount, preProcessingMillis, computeMillis, postProcessingMillis, componentDistribution, configuration
        """

        summ_res = queryToServer(query=wcc_summ)

        print('Number of components identified:',summ_res[0]['componentCount'])

        #5. Drop the graph from memory:
        try:
            drop_graph = """
            CALL gds.graph.drop('myGraph')
            """
            graph_dropped = queryToServer(query=drop_graph)
        except:
            print("WCC Graph not found")
        else:
            print("WCC Analysis Completed")

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

        stat_res = wcc_stats(wcc_res)
        print(stat_res)

        return wcc_res

    def cleanUp(self):
        delete_CloneRel = f"""
        MATCH (n:{self.exp_id})-[r:{self.clone_relation}]-(m:{self.exp_id})
        DELETE r
        """

        clonDel = queryToServer(query=delete_CloneRel)

        check_deleted = f"""
        MATCH (n:{self.exp_id})-[r:{self.clone_relation}]-(m:{self.exp_id})
        RETURN r
        """

        checkRes = queryToServer(query=check_deleted)
        if not checkRes:
            print("Generic cloned relationships deleted")


        delete_TextLabels = f"""
        MATCH (n:{self.common_text})
        REMOVE n:{self.common_text}
        """
        textDel = queryToServer(query=delete_TextLabels)

        check_TextDel = f"""
        MATCH (n:{self.common_text})
        RETURN count(n)
        """
        if not check_TextDel:
            print("Common Text labels deleted")


    def kgSubgraph(self):
        self.dataLoad()

        print('Marking results in kg subgraph')

        loadQuery = f"""
        // Load the genes and pathways from CSV files
        WITH $gene_list as gene_list, $path_list as path_list
        UNWIND gene_list as geneName
        MATCH (g:Genes)-[t:belongs_to]->(p:Pathway)
        WHERE p.name IN path_list and g.name=geneName
        SET g:{self.exp_id}, t.tags = coalesce(t.tags, []) + '{self.exp_id}', p:{self.exp_id}
        WITH g, p, t, gene_list
        OPTIONAL MATCH (g)-[r]-(g2:Genes)
        WHERE r.Pathway = p.name AND g2.name IN gene_list
        SET r.tags = coalesce(r.tags, []) + '{self.exp_id}'
        WITH g
        OPTIONAL MATCH (g)-[c:CONTAINS]->(tn:TextNode)
        WHERE g.Function IS NOT NULL
        SET tn:{self.exp_id}, c.tags = coalesce(c.tags, []) + '{self.exp_id}'
        RETURN g
        """
        path_list = list(self.path_Data.keys())
        gene_list = list(self.gene_Data.keys())

        load_results = cQueryToServer(query=loadQuery, parameters={"path_list":path_list, "gene_list": gene_list})

        test = f"""
        MATCH (n:{self.exp_id})-[r]->(m:{self.exp_id})
        WHERE '{self.exp_id}' IN r.tags
        RETURN n,r,m
        """

        test_results = queryToServer(query=test)

        if test_results and 'n' in test_results[0] and test_results[0]['n']:
            print('Marking KG Subgraph successful')
        else:
            print('Could not mark KG Subgraph')

        wcc_result = self.kgAnalysis()
        self.wcc_res = wcc_result
        self.scoreText()
        self.cleanUp()

    def retrieval(self):
        retQuery = f"""
        UNWIND $wcc_res AS row
        WITH row.name as entityName, row.componentId as components
        MATCH (g:Genes:{self.exp_id})
        WHERE g.name=trim(entityName) and g.name IS NOT NULL
        MATCH (g)-[:CONTAINS]->(tn:TextNode:{self.exp_id}:{self.scoreString})
        OPTIONAL MATCH (g)-[r]->(g2:Genes:{self.exp_id})
        WHERE '{self.exp_id}' IN r.tags
        OPTIONAL MATCH (g)-[:belongs_to]->(p:Pathway:{self.exp_id})
        MATCH (c:n4sch__Class)-[r2]-(g)
        WITH entityName, components, collect(DISTINCT(r.Pathway)) as PathwayNames,
            collect(DISTINCT CASE WHEN r IS NULL THEN [g.name, type(r), g2.name, p.name] ELSE [g.name, type(r), g2.name, r.Pathway] END) as GeneConnections, collect(DISTINCT(c.name)) as ontology, collect(r2) as classRelationships,
            collect(DISTINCT(tn.Text)) as page_content, collect(DISTINCT(tn.embedding)) as Embedding
        WITH entityName, components, PathwayNames, GeneConnections, ontology, classRelationships, page_content, Embedding
        WHERE size(classRelationships) >= 2
        WITH entityName, components, size(PathwayNames) as HubCount, GeneConnections, page_content, Embedding, ontology
        ORDER BY size(classRelationships) DESC, components, HubCount DESC
        RETURN entityName, components, HubCount, GeneConnections, page_content, Embedding, ontology
        """

        documents = cQueryToServer(query=retQuery, parameters={"wcc_res": self.wcc_res})

        if documents:
            print('Retrieval Successful!')
        else:
            print('Retrieval unsuccessful')

        print([len(embed) for embed in documents[0]['Embedding']])

        from langchain.docstore.document import Document

        DOCUMENTS = []
        for dox in documents:
            doc = Document(page_content=''.join(dox['page_content']),
                        metadata={'Name':dox['entityName'], 'components':dox['components'],
                                    'Significance': self.gene_Data[dox['entityName']]['pFdr'], 'Expression': self.gene_Data[dox['entityName']]['teststat'],
                                    'HubCount': dox['HubCount'], 'GeneConnections': dox['GeneConnections'],
                                    'Embeddings': dox['Embedding'], 'Ontology': dox['ontology']})
            DOCUMENTS.append(doc)

        from collections import defaultdict

        grouped_documents = defaultdict(list)
        for doc in DOCUMENTS:
            grouped_documents[doc.metadata['components']].append(doc)

        return grouped_documents

