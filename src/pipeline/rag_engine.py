import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.graphs import Neo4jGraph
from langchain_community.chains.graph_qa.cypher import GraphCypherQAChain 
from langchain_core.prompts import PromptTemplate
from dotenv import load_dotenv

load_dotenv()

class LoreReasoner:
    def __init__(self):
        self.graph = Neo4jGraph(
            url = os.getenv("NEO4J_URI"),
            username = os.getenv("NEO4J_USERNAME"),
            password = os.getenv("NEO4J_PASSWORD")
        )
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)

        self.cypher_generation_template = """
        Task: Generate Cypher statement to query a graph database.
        Instructions:
        - Use only the provided relationship types and properties in the schema.
        - Do not use any other relationship types or properties that are not provided.
        - The relationship types are always in SCREAMING_SNAKE_CASE (e.g., ALLIED_WITH).
        - The nodes are always labeled :Entity.
        - The primary property is 'name'.
        
        Schema:
        {schema}
        
        Question: {question}
        Cypher Query:
        """

        cypher_prompt = PromptTemplate(
            input_variables=['schema', 'question'],
            template=self.cypher_generation_template
        )

        self.chain = GraphCypherQAChain.from_llm(
            llm = self.llm,
            graph = self.graph,
            cypher_prompt = cypher_prompt,
            verbose=True,
            allow_dangerous_requests=True
        )

    def ask(self, question: str) -> str:
        try:
            result = self.chain.invoke(question)
            return result['result']
        except Exception as e:
            return f"Error processing question: {e}"
    
if __name__ == "__main__":
    reasoner = LoreReasoner()
    question = "Explain the background of King Deshret."
    answer = reasoner.ask(question)
    print(f"Q: {question}\nA: {answer}")