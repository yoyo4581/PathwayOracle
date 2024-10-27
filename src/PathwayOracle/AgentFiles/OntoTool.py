from typing import Optional, Type

from langchain.callbacks.manager import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)

# Import things that are needed generically
from pydantic import BaseModel, Field
from langchain.tools import BaseTool
from AgentFiles.CommonOnto import parseOutInfo
from AgentFiles.TextSearch import get_MultCandidates
from typing import List, Tuple
from db import cQueryToServer, queryToServer


## Ontology network formatted:
fetchOntoNet = """
// Define your list of gene names
WITH $geneList AS geneNames

// Match the gene nodes
MATCH (g:Genes)
WHERE g.name IN geneNames

// Find the shortest paths between all pairs of gene nodes through ontology nodes
WITH geneNames, g AS g1
MATCH (g1)-[r:involved_in]->(o1:n4sch__Class)
MATCH (g2:Genes)-[r1:involved_in]->(o2:n4sch__Class)
WHERE g2.name IN geneNames AND g1 <> g2 AND o1 <> o2
WITH g1, g2, o1, o2, r, r1, geneNames
MATCH path = shortestPath((o1)-[:n4sch__SCO*..5]-(o2))
WITH nodes(path) AS pathNodes, relationships(path) AS pathRels
UNWIND range(0, size(pathNodes)-2) AS idx
WITH pathNodes[idx] AS fromNode, pathNodes[idx+1] AS toNode, pathRels[idx] AS rel
WITH CASE WHEN startNode(rel) = fromNode THEN fromNode.name ELSE toNode.name END AS fromNodeName,
     CASE WHEN startNode(rel) = fromNode THEN toNode.name ELSE fromNode.name END AS toNodeName
RETURN DISTINCT fromNodeName, toNodeName
"""

## Possible interactions
fetchGeneInt = """
// Define your list of gene names
WITH $geneList AS geneNames
MATCH (g)-[r]->(g1:Genes)
WHERE g.name in geneNames and g1.name in geneNames
RETURN g.name as gene1, type(r) as relat, r.Pathway as Pathway, g1.name as gene2
"""

## Base ontologies
fetchBaseOnto = """
// Define your list of gene names
WITH $geneList AS geneNames

// Match the gene nodes
MATCH (g:Genes)
WHERE g.name IN geneNames

// Find the shortest paths between all pairs of gene nodes through ontology nodes
WITH geneNames, g
MATCH (g)-[r:involved_in]->(o1:n4sch__Class)
RETURN g.name as geneName, type(r) as reltype, o1.name as baseOnto
"""

def get_commonly(entity: List[str]) -> str:
    candidates = get_MultCandidates(entity)
    for candidate in candidates:
        if not candidate['candidate']:
            return f"No information was found about the gene {candidate['candidate']} in the database"
        elif isinstance(candidate['candidate'], list):
            newline = "\n"
            return (
                "Need additional information, which of these "
                f"did you mean: {newline + newline.join(str(d) for d in candidates)}"
            )

    gene_names = [candidate['candidate'] for candidate in candidates if candidate['label']=='Genes']
    gene_types = [candidate['label'] for candidate in candidates ]
    print('gene_names', gene_names, 'gene_types', gene_types)
    
    getOntoNet = cQueryToServer(query=fetchOntoNet, parameters={'geneList': gene_names})
    getGeneInt = cQueryToServer(query=fetchGeneInt, parameters={'geneList': gene_names})
    getBaseOnto = cQueryToServer(query=fetchBaseOnto, parameters={'geneList': gene_names})

    result = parseOutInfo(gene_names=gene_names, getGeneInt=getGeneInt, getBaseOnto=getBaseOnto, getOntoNet=getOntoNet)
    
    return result


class CommonGeneInput(BaseModel):
    entity: List[str] = Field(description="gene names mentioned in the question")
    

class CommonGeneTool(BaseTool):
    name: str = "InCommonInformation"
    description: str = (
        "for ontology information about genes"
    )
    args_schema: Type[BaseModel] = CommonGeneInput

    def _run(
        self,
        entity: List[str],
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        return get_commonly(entity)

    async def _arun(
        self,
        entity: List[str],
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool asynchronously."""
        return get_commonly(entity)