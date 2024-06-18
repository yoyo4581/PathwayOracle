from langchain.chains.combine_documents.stuff import StuffDocumentsChain
from langchain.chains.llm import LLMChain
from langchain_core.prompts import PromptTemplate
from langchain.chains.combine_documents.map_reduce import MapReduceDocumentsChain, ReduceDocumentsChain
from langchain_text_splitters import CharacterTextSplitter
from langchain.docstore.document import Document
from .db import connect_to_LLM
from sklearn.feature_extraction.text import TfidfVectorizer
import hdbscan
from nltk.stem import PorterStemmer
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from collections import Counter
import numpy as np
import matplotlib.pyplot as plt


class LLM_Summ:

    # Map
    map_template = """
    You are an expert Biochemist that summarizes document information in a clear, concise, and descriptive manner.
    You are able to link mechanisms of gene entities to other gene entities in a consistent manner.
    The following is a set of documents describing a gene entity, it's expression level, and it's role:
    {docs}
    Based on this list of docs, please provide a summary of the mechanism of action of this gene entity. 
    The format of the document follows:
    1. The Name header indicates which gene entity the document refers to.
    2. The Page Content is text data that shows the mechanism of action of this gene entity.
    3. The Interactions header has data that should be treated like a list. The list may contain 4 elements.
    - The first element always indicates the source, 
    - The second and third element may not be present but if they are:
        -the second element indicates the relationship, 
        -the third element indicates the gene entity destination. 
    - The last element should always be the pathway.
    - An interaction between gene entities must have 4 elements in this list. Otherwise the entity simply belongs to a certain pathway.
    4. The Ontology header represents key biological processes topics that this gene may be involved in. Only pick relevant ontologies.
    5. The Expression header tells you how differentially expressed this particular gene is.
    6. The HubCount header value tells you how important this gene is to the overall interaction.

    In your response maintain gene entities that interact with one another and their relationship via the info in the Header field.
    Please prioritize gene entities that have a higher number in the HubCount field.
    Also provide a relative evaluation of the expression levels in each document by using the Expression field these can be:
    (strong positive expression, moderate positive expression, low expression, moderate negative expression, strong negative expression)
    Allow terms in the ontology to guide your summary. The summary should still be sourced from mechanisms found in the Page Content.

    Be as thorough yet succinct as you can. Only rely on information found within this document. 
    Helpful Answer:"""

    # Reduce
    reduce_template = """The following is set of summaries:
    {docs}
    Take these and distill it into a final thoroughly detailed summary that covers all gene entities, formatted not in bulleted form.
    For entities that directly interact with one another and not just belong to a pathway,
    group their mechanisms together and reason how they may work together, including their relationship to one another.
    Finally make a note on how this information is implicated with breast cancer, if it is implicated in breast cancer.
    Feel free to note if it is not, therefore its necessary to provide a balanced response.
    For your assessment on breast cancer implication use sources from PubMed. 

    Provide a score out of 10 for any entity's implications with breast cancer and a score for the certainty of your statements in a consistent style that replicates this example.
    Ex:
    Implication (Gene Entity): X/10
    Certainty (Gene Entity): X/10

    Helpful Answer:"""

    def __init__(self, groupedDocuments, subject):
        self.groupedDocuments = groupedDocuments
        self.llm = None
        self.subject = subject
    
    def llm_connect(self, key):
        self.llm = connect_to_LLM(llm_opt=key)
    
    def generate_FullText(self, docs):
        document_list = []
        for doc in docs:
            full_text = ''
            page_content = 'Page Content:\n'+' '+doc.page_content+'\n'
            Name = 'Name:\n'+' '+ doc.metadata['Name']+'\n'
            Components = 'Components:\n'+' '+str(doc.metadata['components'])+'\n'
            Expression = 'Expression:\n'+' '+str(doc.metadata['Expression'])+'\n'
            PathwayCount = 'HubCount:\n'+' '+ str(doc.metadata['HubCount'])+'\n'
            unique_Data = [' '.join([str(item) for item in x if item is not None]) for x in set(tuple(x) for x in doc.metadata['GeneConnections']) if x]
            
            Interactions = 'Interactions:\n'+' '+ '\n'.join(unique_Data)+'\n'
            Ontology = 'Ontology:\n'+' '+'\n'.join(doc.metadata['Ontology'])
            full_text = full_text + page_content + Name + Components+ Expression + PathwayCount + Interactions + Ontology +'\n'
            dox = Document(page_content = full_text)
            document_list.append(dox)
        
        return document_list
    
    def standardSummaries(self, component, docs):
        docString = './'+self.subject+'/component_'+str(component)
        print(f"Component: {component}")
        genes_involved = [x.metadata['Name'] for x in docs]
        print(f"Genes Involved: {' '.join(genes_involved)} ")
        pathways = []
        interactions = []
        for doc in docs:
            for connect in doc.metadata['GeneConnections']:
                pathways.append(connect[3])
                interactions.append(connect)
        print(f"Pathways Involved: ")
        for path in set(pathways):
            print(path)
        print('\n')
        print(f"Interactions Involved: {interactions}")
        print("\n")
            
        processed_Docs = self.generate_FullText(docs)
        result = self.map_reduce_chain.invoke(processed_Docs)['output_text']
        print(result)
        print('\n \n \n')
        return result


    def largeSummaries(self, component, docs):
        print(f"Conducting ontological clustering for large component {component}")
        # Extract the ontological terms for the documents in component 0
        ontologies = [doc.metadata['Ontology'] for doc in self.groupedDocuments[0]]

        # Convert the list of ontological terms for each document to a single string
        ontologies = [" ".join(ontology) for ontology in ontologies]
        genes = [doc.metadata['Name'] for doc in self.groupedDocuments[component]]
        storeSumm = {}

        def popNetMatrix(doc_Comp):
            num_documents = len(doc_Comp)
            genes = [doc.metadata['Name'] for doc in doc_Comp]
            matrix = np.zeros((num_documents, num_documents))

            for idx in range(len(doc_Comp)):
                subj_name = doc_Comp[idx].metadata['Name']
                for interAct in doc_Comp[idx].metadata['GeneConnections']:
                    if interAct[2]!=None and interAct[2] in genes:
                        obj_name = interAct[2]
                        objLoc = genes.index(obj_name)
                        matrix[idx][objLoc] = 1

            # Create a new figure with a specified size (width, height)
            plt.figure(figsize=(10, 10))
            # Create a heatmap using matplotlib
            plt.imshow(matrix, cmap='gray_r', interpolation='nearest')
            
            # Label the axes with the gene names
            plt.xticks(np.arange(len(genes)), genes, rotation=90)
            plt.yticks(np.arange(len(genes)), genes)
            
            # Add a colorbar and a title
            plt.colorbar(label='Interaction')
            plt.title('Gene Interaction Network')
            
            # Show the plot
            plt.show()
            
            return matrix
        
        def matrixTraverse(popMatrix, sub_row, gene_sub, geneList, visited=None):
            if visited is None:
                visited = set()  # Keep track of visited nodes

            if sub_row >= len(popMatrix):  # Base case: if sub_row is out of range, stop recursion
                return geneList

            for intIdx in range(len(popMatrix[sub_row])): #iterates through columns
                if popMatrix[sub_row][intIdx] == 1 and intIdx not in visited: #check if interaction is present and not visited
                    visited.add(intIdx)  # Mark the node as visited
                    if genes[sub_row] not in gene_sub: #if interaction not already covered
                        gene_sub.append(genes[sub_row])  #append it
                    if genes[intIdx] not in gene_sub:
                        gene_sub.append(genes[intIdx])
                    matrixTraverse(popMatrix, intIdx, gene_sub, geneList, visited) #explore the next link.
            
            # If all paths have been explored, move to the next row
            if all(popMatrix[sub_row][i] == 0 or genes[i] in gene_sub for i in range(len(popMatrix[sub_row]))):
                if gene_sub not in geneList and gene_sub:
                    geneList.append(gene_sub) #once covered append to master
                matrixTraverse(popMatrix, sub_row + 1, [], geneList, visited)
            
            return geneList
        

        def check_value_in_dict(my_dict, my_string):
            for key, value in my_dict.items():
                if key != -1 and my_string in value:
                    return key
            return

        def most_common_except_none(my_list):
            counter = Counter(x for x in my_list if x is not None)
            if counter:
                return counter.most_common(1)[0][0]
            else:
                return


        def cluster_patch(compDocuments, clusters):
            clusterDict = {}
            for docIdx in range(len(clusters)):
                if clusters[docIdx] not in clusterDict:
                    clusterDict[clusters[docIdx]] = []
                clusterDict[clusters[docIdx]].append(compDocuments[docIdx].metadata['Name'])

            for noiseName in clusterDict[-1]: #iterate through the noise genes
                for row in interList: #iterate through the interaction list of lists
                    if noiseName in row: #if a noise gene is in an interaction list
                        #print('NoiseName', noiseName)
                        othergenes = [gene for gene in row if gene != noiseName] #get all genes in interaction list aside from Noise gene
                        clusterPop = [check_value_in_dict(clusterDict, gene) for gene in othergenes ] # create a list of cluster membership except -1
                        mostCommon = most_common_except_none(clusterPop)  #identify the most common cluster membership
                        for docIdx in range(len(clusters)):
                            if compDocuments[docIdx].metadata['Name'] == noiseName:
                                if mostCommon!=None:
                                    clusters[docIdx] = mostCommon
            return clusters

        # Define a stemming tokenizer
        def stemming_tokenizer(text):
            stemmer = PorterStemmer()
            stop_words = set(stopwords.words('english'))
            return [stemmer.stem(w) for w in word_tokenize(text) if w not in stop_words]

        def vectorize(compDocuments, cluster_size=10):
            print('Attempting with min_cluster size of :',cluster_size)
            # Create a TF-IDF vectorizer and transform the ontological terms
            vectorizer = TfidfVectorizer(tokenizer=stemming_tokenizer)
            X = vectorizer.fit_transform(ontologies)
            
            # Apply HDBSCAN clustering
            hdbscan_cluster = hdbscan.HDBSCAN(min_cluster_size=cluster_size)  # Choose an appropriate minimum cluster size
            clusters = hdbscan_cluster.fit_predict(X.toarray())
            if 0 in set(clusters):
                clustersPatched = cluster_patch(compDocuments, clusters)
                return clustersPatched
            else:  
                return clusters

        def checkClusterSize(compDocuments, clusters):
            clusterMembership = {}
            tooLarge = False
            for cluster in set(clusters):
                if cluster==-1:
                    continue
                clusterMembership[cluster] = 0
                for idx in range(len(clusters)):
                    if clusters[idx]==cluster:
                        clusterMembership[cluster] += 1

            for k, v in clusterMembership.items():
                print(k, v)
                if v > 14:
                    tooLarge = True
                    
            return tooLarge
        
        def vectorTune(compDocuments):
            clusters = vectorize(compDocuments)
            clusterSet = set(clusters)
            n = 0
            tooLarge = checkClusterSize(compDocuments, clusters)

            # Increasing cluster resolution when the clustering has failed or when any cluster is too large
            while 0 not in clusterSet or tooLarge:
                n = n+1
                clusters = vectorize(compDocuments, 10-n)
                clusterSet = set(clusters)
                tooLarge = checkClusterSize(compDocuments, clusters)
                print(clusterSet)
            
            # The clusters variable contains the assigned cluster for each document

            return clusters
        
        def vectorSummarize(clustered):
            clusterSet = set(clustered)
            for cluster in clusterSet:
                #Cluster Name
                clust_names = []
                for idx in range(len(clustered)):
                    if clustered[idx]==cluster:
                        clust_names.append(self.groupedDocuments[0][idx].metadata['Name'])      
            
                print('Cluster: ', cluster, 'Names: ', ' '.join(clust_names))
                ontoList = []
                for name in clust_names:
                    for doc in self.groupedDocuments[0]:
                        if doc.metadata['Name'] == name:
                            for onto in doc.metadata['Ontology']:
                                ontoList.append(onto)
            
                
                print('Num of ontologies: ', len(ontoList), ' Ontologies in-common: ', len(ontoList)-len(list(set(ontoList))))

        netMatrix = popNetMatrix(self.groupedDocuments[component])

        interList = matrixTraverse(netMatrix, 0, [], [])
    
        clusters = vectorTune(self.groupedDocuments[component])
        vectorSummarize(clusters)

        for clust in set(clusters):      
            strBuild = ''
            print(f'Cluster: {clust}\n')
            strBuild = strBuild+f'Cluster: {clust}\n' 
            indices = [i for i in range(len(clusters)) if clusters[i] == clust] 
            selDocs = [docs[x] for x in indices]
            genes_involved = [x.metadata['Name'] for x in selDocs]
            print(f"Genes Involved: {' '.join(genes_involved)}\n")
            strBuild = strBuild+f"Genes Involved: {' '.join(genes_involved)}\n"
            pathways = []
            interactions = []
            for doc in selDocs:
                for connect in doc.metadata['GeneConnections']:
                    pathways.append(connect[3])
                    if connect[2] in genes_involved:
                        interactions.append(connect)
            print(f"Pathways Involved:\n")
            strBuild = strBuild+f"Pathways Involved:\n"
            for path in set(pathways):
                print(path)
                strBuild = strBuild+path
            print('\n')
            strBuild = strBuild+'\n'
            print(f"Interactions Involved: {interactions}\n")
            strBuild = strBuild+f"Interactions Involved: {interactions}\n"

            print('\n')
            strBuild = strBuild+'\n'
            
            processed_Docs = self.generate_FullText(selDocs)
            strBuild = strBuild+self.map_reduce_chain.invoke(processed_Docs)['output_text']
            print(self.map_reduce_chain.invoke(processed_Docs)['output_text'])
            print('\n \n \n')
            strBuild = strBuild+'\n \n \n'
            
            storeSumm['Component_'+str(component)+'_Clust_'+str(clust)] = strBuild

        return storeSumm
    
    def rerank_Summ(self, store):
        import re

        rankedStore = {}

        def parseMaxScore(text):
            result = re.findall(r'[iI]mplicat[ioned]\s*.*?(\d)\/10', text)
            print(text)
            print(result)
            if result:
                max_ImpScore = max(result)
            else:
                max_ImpScore = None
            return max_ImpScore
        
        for key, val in store.items():
            impScore = parseMaxScore(val)
            print(impScore)
            rankedStore[key] = (val, impScore)

        return rankedStore
    
    def to_Doc(self, store):
        import os 
        preString = os.getcwd()
        print('Writing txt files to directory', os.getcwd())
        for key, val in store.items():
            fileString =preString + '/'+str(key)+'_'+str(val[1])+'.txt'
            f = open(fileString, 'w')
            f.write(str(val[0]))
            f.close()

        return store


    def generateSumm(self, to_write=False):
        self.map_prompt = PromptTemplate.from_template(self.map_template)
        self.reduce_prompt = PromptTemplate.from_template(self.reduce_template)
        self.map_chain = LLMChain(llm=self.llm, prompt=self.map_prompt)
        # Reduce
        self.reduce_chain = LLMChain(llm=self.llm, prompt=self.reduce_prompt)

        # Takes a list of summarized documents, combines them into a single string, and passes this to an LLMChain
        combine_documents_chain = StuffDocumentsChain(
            llm_chain= self.reduce_chain, 
            document_variable_name="docs"
        )

        # Combines and iteratively reduces the summarized documents
        reduce_documents_chain = ReduceDocumentsChain(
            # This is final chain that is called.
            combine_documents_chain=combine_documents_chain,
            # If documents exceed context for `StuffDocumentsChain`
            collapse_documents_chain=combine_documents_chain,
            # The maximum number of tokens to group documents into.
            token_max=10000,
        )

        # Combining documents by mapping a chain over them, then combining results
        self.map_reduce_chain = MapReduceDocumentsChain(
            # Map chain
            llm_chain=self.map_chain,
            # Reduce chain
            reduce_documents_chain=reduce_documents_chain,
            # The variable name in the llm_chain to put the documents in
            document_variable_name="docs",
            # Return the results of the map steps in the output
            return_intermediate_steps=False,
        )

        all_store = {}

        for component, docs in self.groupedDocuments.items():
            componentSize = len(self.groupedDocuments[component])
            if componentSize > 20:
                storeSumm = self.largeSummaries(component, docs)
                for key, val in storeSumm.items():
                    all_store[key] = val
            else:
                all_store['Component_'+str(component)] = self.standardSummaries(component, docs)

        ranked_store = self.rerank_Summ(all_store)

        if to_write:
            self.to_Doc(ranked_store)

        return ranked_store
        

