import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

class Neo4jClient:
    def __init__(self):
        self.uri = os.getenv("NEO4J_URI")
        self.username = os.getenv("NEO4J_USERNAME")
        self.password = os.getenv("NEO4J_PASSWORD")
        self.database = os.getenv("NEO4J_DATABASE")
        self.driver = None

    def connect(self):
        try:
            # Add a connection timeout
            self.driver = GraphDatabase.driver(
                self.uri, 
                auth=(self.username, self.password),
                connection_timeout=30 # 30 seconds
            )
            
            self.driver.verify_connectivity()

            print("Successfully connected to Neo4j!")
        except Exception as e:
            print(f"Connection failed!")
            print(f"Error details: {e}")
            print(f"Target URI: {self.uri}")
    
    def close(self):
        if self.driver:
            self.driver.close()

    def query(self, cypher_query, parameters=None):
        if not self.driver:
            raise RuntimeError("Database connection is not established.")
        with self.driver.session() as session:
            result = session.run(cypher_query, parameters)
            return result.data()
        
if __name__ == "__main__":
    client = Neo4jClient()
    client.connect()
    client.close()