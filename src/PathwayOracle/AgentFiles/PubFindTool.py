from typing import Optional, Type, List

from langchain.callbacks.manager import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)

# Import things that are needed generically
from pydantic import BaseModel, Field
from langchain.tools import BaseTool
from AgentFiles.TextSearch import get_MultCandidates, generate_full_text_query
from AgentFiles.BertEmbeddings import bio_bert_embeddings
from db import cQueryToServer, queryToServer



cypher_gene_search = """
WITH $queryEmbed as queryEmbedding, $fulltextQuery_list as fulltextQuery_list
UNWIND fulltextQuery_list as fulltextQuery
MATCH (g:Genes {name: $geneName})-[:INFO]->(a:Abstract)
WITH collect(a) as abstractNodes, g, fulltextQuery, queryEmbedding
CALL db.index.fulltext.queryNodes('absText', fulltextQuery)
YIELD node, score
WHERE node in abstractNodes
WITH g.name as geneName, node, queryEmbedding, apoc.coll.partition(node.sentenceEmbed, node.shape[1]) AS partitionedEmbeddings, fulltextQuery
UNWIND partitionedEmbeddings AS sentenceEmbedding
WITH node, collect(geneName) as geneMem, vector.similarity.cosine(sentenceEmbedding, queryEmbedding) AS score, fulltextQuery
RETURN DISTINCT node.text as text, MAX(score) as maxScore, node {.*, text:Null, sentenceEmbed: Null, id:Null, from:geneMem } as metadata
ORDER BY maxScore DESC 
"""


def get_pub_linked_info(entity: str, entity_linked: List[str], subject_phrases: List[str]) -> str:
    queryEmbedding = bio_bert_embeddings.embed_query(entity).tolist()
    
    candidates = get_MultCandidates(entity_linked)

    print(entity, entity_linked, subject_phrases, candidates)

    for candidate in candidates:
        if not candidate['candidate']:
            return f"No information was found about the entity {candidate['candidate']} in the database"
        elif isinstance(candidate['candidate'], list):
            newline = "\n"
            return (
                "Need additional information, which of these "
                f"did you mean: {newline + newline.join(str(d) for d in candidates)}"
            )

    candidate_names = [candidate['candidate'] for candidate in candidates]
    candidate_types = [candidate['label'] for candidate in candidates]

    subjectQuery_list = [ generate_full_text_query(phrase) for phrase in subject_phrases ]

    all_data = []
    for cand_idx in range(len(candidate_names)):

        print('candidate_types[cand_idx]', candidate_types[cand_idx])
        print('candidate_names[cand_idx]', candidate_names[cand_idx])

        if candidate_types[cand_idx] == 'Genes':
            data = cQueryToServer(
                query=cypher_gene_search, parameters={"queryEmbed": queryEmbedding, "geneName": candidate_names[cand_idx], "fulltextQuery_list": subjectQuery_list}
            )
            all_data.extend(data)


    fullString = ''
    if not all_data:
        return "No information was found about the question you asked."
        
    for r in all_data:
        if r['maxScore'] >= 0.85:
            from_genes = ', '.join(r['metadata'].get('from', []))
            pmid = r['metadata'].get('pmid', 'N/A')
            text = r.get('text', '')
            pubString = f'Genes: {from_genes}\nPublication PubMedId: {pmid}\n{text}\n'
            fullString += pubString
    
    result = fullString
    return result


class PublicationLinkedInput(BaseModel):
    entity: str = Field(description="the question itself")
    entity_linked: List[str] = Field(description="any gene specified in the question. Dont include the term 'gene'.")
    subject_phrases: List[str] = Field(description="Extract key concepts and common phrases from the subject, excluding the gene name. \
Make sure to include the base phrase and variations that are found in the subject string. \
For example, for the subject 'age-effect in infiltrating ductal breast cancer': \
Answer: ['age-effect', 'infiltrating ductal breast cancer', 'breast cancer', 'ductal breast cancer', 'age-effect cancer', 'age-effect infiltrating ductal breast cancer'].")


class PubInfoLinkedTool(BaseTool):
    name: str = "PubInfoLinkedTool"
    description: str = (
        "for publication information about genes. Use in questions only with the term 'publication'."
    )
    args_schema: Type[BaseModel] = PublicationLinkedInput

    def _run(
        self,
        entity: str,
        entity_linked: List[str],
        subject_phrases: List[str],
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        return get_pub_linked_info(entity, entity_linked, subject_phrases)

    async def _arun(
        self,
        entity: str,
        entity_linked: List[str],
        subject_phrases: List[str],
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool asynchronously."""
        return get_pub_linked_info(entity, entity_linked, subject_phrases)
