from AgentFiles.Agent import agent_executor
from typing import List, Tuple
from db import cQueryToServer
from collections import defaultdict
from langchain.docstore.document import Document


class AgentRetrieval:
    def __init__(self, subject, wcc_res, instance_id):
        self.subject = subject.replace("_", " ")
        self.wcc_res = wcc_res
        self.instance_id = instance_id
        self.linkDocs, self.genePathwayMap, self.paData_complete = self.linkDocuments()


    def linkDocuments(self):
        interactionsInfo = """
        MATCH (i:Instance {instance_id: $instance_id})-[r]->(n:Genes)
        WITH collect(n) as all_nodes, i
        UNWIND all_nodes as node
        MATCH (node:Genes)-[b]-(h)
        WHERE h in all_nodes AND i.instance_id in b.instance_ids
        RETURN DISTINCT node.name as geneName, id(node), id(startNode(b)), id(endNode(b)), id(h), type(b) as relType, h.name as connectedNode, coalesce(b.Pathway, null) as Pathway
        """
        interactionData= cQueryToServer(query=interactionsInfo, parameters = {'instance_id': self.instance_id})
        print(interactionData)

        pathwaysInfo = """
        MATCH (i:Instance {instance_id: $instance_id})-[r]->(n:Genes)
        WITH collect(n) as all_nodes, i
        UNWIND all_nodes as node
        MATCH (node:Genes)-[b]-(h:Pathway)
        WHERE i.instance_id in b.instance_ids
        RETURN node.name as geneName, collect(h.name) as Pathways
        """
        pa_DataQuery = """
        MATCH (i:Instance {instance_id: $instance_id})-[r]-(g:Genes)
        RETURN g.name as geneName, r.significance as Sig, r.expression as Exp
        """
        gene_pathway_data = cQueryToServer(query= pathwaysInfo, parameters= {'instance_id': self.instance_id})
        pa_Data = cQueryToServer(query=pa_DataQuery, parameters={'instance_id': self.instance_id})

        paData_complete = { paEntry['geneName'] : {'Sig' : float(paEntry['Sig']), 'Exp': float(paEntry['Exp'])} for paEntry in pa_Data }


        gene_pathway_map = {entry['geneName'] : entry['Pathways'] for entry in gene_pathway_data}

        def reorganize_wcc(wcc_res, linkDocs):

            def filter_wcc_res(wcc_res):
                filtered_wcc_res = {}

                for key, gene_list in wcc_res.items():
                    # Filter out non-gene entries (those that are not all uppercase)
                    filtered_genes = [gene for gene in gene_list if gene.isupper()]
                    
                    # Only add to the filtered dictionary if there are valid gene names
                    if filtered_genes:
                        filtered_wcc_res[key] = filtered_genes

                return filtered_wcc_res

            # Example usage:
            filtered_wcc_res = filter_wcc_res(wcc_res)

            # Step 1: Create an adjacency list from linkDocs
            adjacency_list = defaultdict(list)

            intX_StringStore = defaultdict(list)
            
            # Build the adjacency list based on interactions in linkDocs
            for doc in linkDocs:
                gene1 = doc['geneName']
                gene2 = doc['connectedNode']

                # Add both forward and reverse directions to the adjacency list (undirected)
                adjacency_list[gene1].append(gene2)
                adjacency_list[gene2].append(gene1)

                # Check the direction of the interaction based on start and end node IDs to keep track of directionality
                if doc['id(node)'] == doc['id(startNode(b))']:  # Forward direction
                    intX_StringStore[gene1].append(f"Gene {gene1} is a {doc['relType']} of Gene {gene2} in the Pathways: {doc['Pathway']}")
                    intX_StringStore[gene2].append(f"Gene {gene1} is a {doc['relType']} of Gene {gene2} in the Pathways: {doc['Pathway']}")
                else:  # Reverse direction
                    intX_StringStore[gene2].append(f"Gene {gene2} is a {doc['relType']} of Gene {gene1} in the Pathways: {doc['Pathway']}")
                    intX_StringStore[gene1].append(f"Gene {gene2} is a {doc['relType']} of Gene {gene1} in the Pathways: {doc['Pathway']}")


            # Step 2: Reorganize wcc_res into subcomponents based on connections in linkDocs
            new_wcc_res = defaultdict(lambda: defaultdict(list))  # Structure: {component_index: {subcomponent_index: [genes]}}
            
            # Helper function for Depth-First Search (DFS) to find connected genes
            def dfs(gene, visited, current_subcomponent, genes_in_component):
                stack = [gene]
                while stack:
                    current_gene = stack.pop()
                    if current_gene not in visited:
                        visited.add(current_gene)

                        # Create a dictionary for the gene containing its name and its neighbors
                        gene_object = {
                            'name': current_gene,
                            #Directly connected neighbor
                            'neighbors':adjacency_list[current_gene],
                            'intString': intX_StringStore[current_gene]
                        }
                        current_subcomponent.append(gene_object)
                        
                        # Add neighbors (connected genes) that are part of the current component
                        for neighbor in adjacency_list[current_gene]:
                            if neighbor not in visited and neighbor in genes_in_component:
                                stack.append(neighbor)

            # Step 3: Iterate over each component in wcc_res
            for component_index, genes in filtered_wcc_res.items():
                visited = set()
                subcomponent_index = 0
                
                # Iterate over all genes in the current component
                for gene in genes:
                    if gene not in visited:
                        # Create a new subcomponent for the connected genes
                        current_subcomponent = []
                        dfs(gene, visited, current_subcomponent, genes)  # Run DFS to find all connected genes
                        
                        # Save the subcomponent in the new_wcc_res structure
                        new_wcc_res[component_index][subcomponent_index] = current_subcomponent
                        subcomponent_index += 1
            
            return new_wcc_res
    
        new_wcc_structure = reorganize_wcc(wcc_res= self.wcc_res, linkDocs=interactionData)
        return new_wcc_structure, gene_pathway_map, paData_complete

    def agentCommunicate(self, component_Select: dict = None):
        # Initialize component_Select if it's None
        component_Select = component_Select or {}

        for outer_key, inner_dict in self.linkDocs.items():
            if outer_key not in component_Select:
                # Add all inner keys if outer key is not in component_Select
                component_Select[outer_key] = list(inner_dict.keys())
            else:
                # If user provides specific subcomponent keys, check their validity
                provided_inner_keys = component_Select[outer_key] or inner_dict.keys()
                
                # Retain only valid subcomponent keys
                valid_inner_keys = [key for key in provided_inner_keys if key in inner_dict]
                
                # Warn only if any provided subcomponent key doesn't exist
                invalid_keys = [key for key in provided_inner_keys if key not in inner_dict]
                if invalid_keys:
                    print(f"Warning: Subcomponent keys {invalid_keys} not found under '{outer_key}'. Valid keys: {inner_dict.keys()}")

                component_Select[outer_key] = valid_inner_keys



        def seriesQuestions(gene, neighborGenes):
            subject = self.subject
            q1 = f'Function: Gene {gene} associates it with the subject {subject}'
            q2 = f'Ontology: Genes {[gene] + neighborGenes} associates it with the subject {subject}'
            q3 = f'Publication: Gene {gene} associates it with the subject {subject}'

            return [q1,q2,q3]

        compoDocs = defaultdict(lambda: defaultdict(list))
        for compo, subCompo_keys in component_Select.items():
            for subCompo_key in subCompo_keys:
                geneEntities = self.linkDocs[compo][subCompo_key]
                
                for geneEntity in geneEntities:
                    geneName = geneEntity['name']
                    directGenes = geneEntity['neighbors']
                    pathways_for_gene = self.genePathwayMap[geneName]

                    # Building initial context
                    context = ''
                    context += ', '.join(pathways_for_gene)
                    context_complete = f'Gene {geneName} is associated with Pathways:' + context
                    context_complete = context_complete + "Interactions:\n" + '\n'.join(geneEntity['intString'])

                    # Adding initial context to chat_history
                    chat_history: List[Tuple[str, str]] = [("user", context_complete)]

                    # Building questions
                    q_list = seriesQuestions(gene = geneName, neighborGenes = directGenes)
                    for question in q_list:
                        chat_history.append(("user", question))
                        response = agent_executor.invoke({"input": question, "chat_history": chat_history})

                        chat_history.append(("assistant", response['output']))
                        # Storing all previous answers to the chat_history.

                        context_complete = context_complete +'\n'+ response['output']

                    context_complete = context_complete + '\n' +'Expression: '+ str(self.paData_complete[geneName]['Exp'])

                    fullDoc = Document(page_content=context_complete, metadata={'Name': geneName, 'Exp':self.paData_complete[geneName]['Exp'], 'Sig': self.paData_complete[geneName]['Sig']})

                    compoDocs[compo][subCompo_key].append(fullDoc)

        return compoDocs