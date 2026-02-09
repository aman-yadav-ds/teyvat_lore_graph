import os
from langchain_neo4j import Neo4jGraph, GraphCypherQAChain
from langchain_core.prompts import PromptTemplate
from langchain_ollama import ChatOllama
from langchain_groq import ChatGroq
from dotenv import load_dotenv

load_dotenv()

class LoreReasoner:
    def __init__(self):
        self.graph = Neo4jGraph(
            url=os.getenv("NEO4J_URI"),
            username=os.getenv("NEO4J_USERNAME"),
            password=os.getenv("NEO4J_PASSWORD")
        )

        self.llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            temperature=0,
            
        )

        # CORRECTED TEMPLATE
        # Notice we use {{name: ...}} for examples so LangChain doesn't crash.
        self.cypher_generation_template = """
        Task: Generate Cypher statement to query a graph database.
        
        Schema:
        {schema}
        
        Instructions:
        1. Use only the provided relationship types and properties in the schema.
        2. Do not use any other relationship types or properties that are not provided.
        3. **Fuzzy Search**: Use `CONTAINS` or `(?i)` for names.
           - Example: MATCH (n:Entity) WHERE n.name =~ '(?i).*Abyss.*' RETURN n
        4. **Wildcard Relations**: If the verb is vague (like "affect"), use undirected relationships.
           - Example: MATCH (a:Entity {{name: 'Abyss'}})-[r]-(b) RETURN type(r), b.name
        
        CRITICAL:
        - Generate ONLY ONE single Cypher query.
        - Do NOT add comments (//).
        - Do NOT use markdown (```).
        
        Question: {question}
        Cypher Query:
        """

        self.cypher_prompt = PromptTemplate(
            input_variables=["schema", "question"], 
            template=self.cypher_generation_template
        )

        self.chain = GraphCypherQAChain.from_llm(
            self.llm,
            graph=self.graph,
            cypher_prompt=self.cypher_prompt,
            verbose=True,
            allow_dangerous_requests=True,
            return_direct=False 
        )

    def ask(self, question):
        try:
            print(f"🤔 Thinking: {question}")
            # .invoke returns a dict, we want the 'result' key
            response = self.chain.invoke({"query": question})
            return response['result']
        except Exception as e:
            return f"I tripped over a vine (Graph Error): {e}"

if __name__ == "__main__":
    bot = LoreReasoner()
    
    # 2. Test "Connection" logic
    print(bot.ask("What is the connections between the Abyss and the World Tree?"))