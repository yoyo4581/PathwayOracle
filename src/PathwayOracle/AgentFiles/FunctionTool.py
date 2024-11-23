from typing import Optional, Type

from langchain.callbacks.manager import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)

# Import things that are needed generically
from pydantic import BaseModel, Field
from langchain.tools import BaseTool
from .TextSearch import get_MultCandidates
from typing import List, Tuple
from ..db import cQueryToServer, queryToServer


description_query = """
WITH $candidates as candidates, $types as labelType
UNWIND range(0, size(candidates) - 1) as idx
WITH candidates[idx] as candidate, labelType[idx] as label
CALL apoc.cypher.run(
  'MATCH (m:`' + label + '`)
   WHERE m.name = $candidate
   MATCH (m)-[r:CONTAINS]-(t)
   WITH m, type(r) as type, collect(coalesce(t.Text, "")) as text
   WITH m, type + ": " + reduce(s = "", x IN text | s + x + ", ") as types
   WITH m, collect(types) as contexts
   WITH m, "type: " + labels(m)[0] + "\ndescription: " + coalesce(m.description, m.name)
       + "\ntype: " + coalesce(m.type, "") + "\n" +
       reduce(s = "", c in contexts | s + substring(c, 0, size(c) - 2) + "\n") as context
   RETURN context LIMIT 1',
  {candidate: candidate}) YIELD value
RETURN value.context as context
"""



def get_function(entity: List[str]) -> str:
    candidates = get_MultCandidates(entity)
    candidate_list = [candidate['candidate'] for candidate in candidates ]
    type_list = [candidate['label'] for candidate in candidates ]

    print('candidate_list', candidate_list, 'type_list', type_list)
    # Assuming candidates is a list of dictionaries with a key "candidate"
    for candidate in candidates:
        if not candidate['candidate']:
            return f"No information was found about the gene {candidate['candidate']} in the database"
        elif isinstance(candidate['candidate'], list):
            newline = "\n"
            return (
                "Need additional information, which of these "
                f"did you mean: {newline + newline.join(str(d) for d in candidates)}"
            )
    data = cQueryToServer(
        query=description_query, parameters={"candidates": candidate_list, "types": type_list}
    )
    result = [ dat["context"] for dat in data ]
    if not result:
        return "No functional information was found about these gene entities."
    
    return result


class FunctionInput(BaseModel):
    entity: List[str] = Field(description="gene names mentioned in the question")


class FunctionTool(BaseTool):
    name: str = "Function"
    description: str = (
        "If the key term 'function' is in the question then use this tool"
    )
    args_schema: Type[BaseModel] = FunctionInput

    def _run(
        self,
        entity: List[str],
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        return get_function(entity)

    async def _arun(
        self,
        entity: List[str],
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool asynchronously."""
        return get_function(entity)