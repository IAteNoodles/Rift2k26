from fastmcp import FastMCP
import mariadb
from neo4j import GraphDatabase
import os
import logging
import socket
import argparse
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- LOGGING CONFIGURATION ---
logger = logging.getLogger("Database-MCP")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s | %(levelname)-8s | %(message)s', datefmt='%H:%M:%S'))
logger.addHandler(ch)

# --- MCP SERVER ---
mcp = FastMCP("Database")

# --- DATABASE CONFIGURATION ---
DB_HOST = os.getenv('DB_HOST')
DB_PORT = int(os.getenv('DB_PORT', 3306))
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')

NEO4J_URI = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
AURA_USER = os.getenv('AURA_USER', 'neo4j')
AURA_PASSWORD = os.getenv('AURA_PASSWORD')

# Global connection status
MARIADB_AVAILABLE = False
NEO4J_AVAILABLE = False
neo4j_driver = None

def init_connections():
    """Establish and verify connections to MariaDB and Neo4j on startup."""
    global MARIADB_AVAILABLE, NEO4J_AVAILABLE, neo4j_driver
    
    # Test MariaDB connection
    try:
        if all([DB_HOST, DB_USER, DB_PASSWORD, DB_NAME]):
            conn = mariadb.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME, port=DB_PORT)
            conn.close()
            MARIADB_AVAILABLE = True
            logger.info(f"✅ MariaDB connected: {DB_HOST}:{DB_PORT}/{DB_NAME}")
        else:
            logger.warning("⚠️ MariaDB environment variables incomplete.")
    except Exception as e:
        logger.warning(f"⚠️ MariaDB connection failed: {e}")

    # Test Neo4j connection
    try:
        if NEO4J_URI:
            neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(AURA_USER, AURA_PASSWORD))
            neo4j_driver.verify_connectivity()
            NEO4J_AVAILABLE = True
            logger.info(f"✅ Neo4j connected: {NEO4J_URI}")
        else:
            logger.warning("⚠️ NEO4J_URI not set.")
    except Exception as e:
        logger.warning(f"⚠️ Neo4j connection failed: {e}")

# =============================================================================
# MCP TOOL DEFINITIONS
# =============================================================================

@mcp.tool("ExecuteQuery")
def execute_query(query: str, db_type: str = "mariadb") -> dict:
    """Execute a query against the pre-configured database.
    
    Args:
        query: The SQL or Cypher query to run.
        db_type: 'mariadb' (default) or 'neo4j'.
    """
    db_type = db_type.lower()
    
    if db_type in ("mariadb", "sql"):
        if not MARIADB_AVAILABLE:
            return {"error": "MariaDB connection not established on server startup."}
        try:
            conn = mariadb.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME, port=DB_PORT)
            cursor = conn.cursor()
            cursor.execute(query)
            if query.strip().upper().startswith("SELECT"):
                columns = [desc[0] for desc in cursor.description]
                results = [dict(zip(columns, row)) for row in cursor.fetchall()]
                conn.close()
                return {"results": results, "count": len(results)}
            else:
                conn.commit()
                affected = cursor.rowcount
                conn.close()
                return {"message": "Success", "affected_rows": affected}
        except Exception as e:
            return {"error": str(e)}

    elif db_type == "neo4j":
        if not NEO4J_AVAILABLE:
            return {"error": "Neo4j connection not established on server startup."}
        try:
            with neo4j_driver.session() as session:
                result = session.run(query)
                records = [record.data() for record in result]
                return {"results": records, "count": len(records)}
        except Exception as e:
            return {"error": str(e)}
    
    return {"error": f"Invalid db_type: '{db_type}'. Must be 'mariadb' or 'neo4j'."}

# =============================================================================
# SERVER RUNNER
# =============================================================================

def get_local_ips(port):
    ips = [f"localhost:{port}", f"127.0.0.1:{port}"]
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.append(f"{s.getsockname()[0]}:{port}")
        s.close()
    except:
        pass
    try:
        hostname = socket.gethostname()
        host_ip = socket.gethostbyname(hostname)
        if host_ip and host_ip not in ips:
            ips.append(f"{host_ip}:{port}")
    except:
        pass
    return list(dict.fromkeys(ips)) # Dedupe preserving order

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Healthcare MCP Server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8069)
    args = parser.parse_args()

    # Pre-connect to databases
    init_connections()

    print("\n" + "="*60)
    print("🏥 DATABASE MCP SERVER STARTED")
    print("="*60)
    print("\n🌐 ACCESS URLS:")
    for ip in get_local_ips(args.port):
        print(f"   http://{ip}/mcp/")
    print("\n📋 Usage Example:\n   mcp.call_tool('ExecuteQuery', {'query': 'SELECT * FROM Patient LIMIT 1'})")
    print("="*60 + "\n")

    mcp.run(transport="streamable-http", host=args.host, port=args.port)
