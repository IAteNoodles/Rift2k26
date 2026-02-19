# PrimeKG-PGx Subgraph & MCP Documentation

This documentation covers the schema, extraction logic, and MCP operations for the Pharmacogenomics (PGx) subgraph extracted from PrimeKG.

## 1. Subgraph Overview
The graph represents a clinical and biological "safety bubble" around 6 core pharmacogenes. It includes all nodes reachable within **3 hops** from these seeds, capturing direct metabolic interactions, drug-drug conflicts, and downstream phenotypic effects.

### Seed Genes (PharmacogeneCore)
- **CYP2D6**: Primary metabolizer for antidepressants, opioids, and antipsychotics.
- **CYP2C19**: Critical for activating antiplatelets (Clopidogrel) and metabolizing PPIs.
- **CYP2C9**: Major metabolizer for Warfarin, Phenytoin, and NSAIDs.
- **SLCO1B1**: Transporter gene (OATP1B1) linked to statin-induced myopathy.
- **TPMT**: Essential for safe dosing of thiopurines (Imuran/6-MP).
- **DPYD**: Rate-limiting enzyme for 5-FU and Capecitabine detoxification.

---

## 2. Graph Schema
The graph is hosted in the Neo4j `drugs` database.

### Node Labels
| Label | Description |
| :--- | :--- |
| `PharmacogeneCore` | One of the 6 seed genes. |
| `Drug` | Chemicals, FDA-approved medications, and investigational compounds. |
| `GeneProtein` | Human genes and their relative proteins. |
| `Disease` | Clinical conditions and disorders. |
| `Phenotype` | Observable traits or symptoms (e.g., "Toxicity", "Bleeding"). |
| `MolecularFunction` | Biochemical activities (from Gene Ontology). |
| `DrugGeneSubgraph` | A universal label for all nodes in this specific extracted subset. |

### Node Properties
- `name`: Common name (e.g., "Warfarin", "CYP2C9").
- `index`: Unique PrimeKG ID (e.g., `Entrez:1559`).
- `node_type`: String category (drug, gene/protein, disease, etc.).
- `hop`: Distance from seed genes (0, 1, 2, or 3).

### Relationship Types & Meanings
| Type | Description | Clinical Significance |
| :--- | :--- | :--- |
| `DRUG_PROTEIN` | Drug targets or metabolizes a protein. | **Metabolic path**: Direct interaction. |
| `DRUG_DRUG` | Known interaction between two medications. | **Conflict**: Potential metabolic competition. |
| `PROTEIN_PROTEIN` | Physical interaction or biochemical pathway. | **Context**: Secondary pathways. |
| `DRUG_EFFECT` | Link between drug and side effect. | **Outcome**: Correlates genes to toxicity. |
| `PHENOTYPE_PROTEIN`| Link between gene and clinical trait. | **Direct Risk**: Predictive risk marker. |

---

## 3. MCP Operations
The `Database` MCP server (port `8069`) provides tools to interface with this graph.

### `ExecuteQuery`
Runs arbitrary Cypher against the graph. Default database is `drugs`.

**Parameters:**
- `query` (str): Cypher/SQL statement.
- `db_type` (str): `"neo4j"` or `"mariadb"`.
- `database` (str, optional): Target database name. Defaults to `drugs`.

### `ListDatabases`
Lists available databases to verify where the KG is loaded.

---

## 4. Query Examples (Cypher)

### Finding Metabolic Paths (Warfarin Example)
Find the shortest path to a core gene and explain the relationship.
```cypher
MATCH (d {name: 'Warfarin'})
MATCH (g:PharmacogeneCore)
MATCH p = shortestPath((d)-[*..3]-(g))
RETURN 
    d.name AS drug, 
    g.name AS gene, 
    [rel in relationships(p) | type(rel)] AS relations,
    [node in nodes(p) | node.name] AS path
```

### Explaining Connectivity
Check how many pathways connect a drug class to our genes:
```cypher
MATCH (n {name: 'Clopidogrel'})-[r]->(target)
RETURN type(r) AS connection_type, target.name AS connected_node, labels(target) AS node_type
```

---

## 5. System Setup
- **Neo4j URI**: `bolt://localhost:7687` (DB: `drugs`)
- **MCP Server**: `http://localhost:8069/mcp/`
- **Environment**: Configuration is managed via the `.env` file in the root directory.
