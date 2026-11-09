# RAG application architecture

![RAG application architecture](architecture.png)

This diagram follows the implemented ingestion (`injection/`) and retrieval
(`retrieval/`) code, including the chat service's DynamoDB memory integration.

```mermaid
flowchart TB
    subgraph ING[Document ingestion - injection/]
        S3["AWS S3<br/>Organizational .txt documents"]
        READ["Read UTF-8 text<br/>Extract document header metadata"]
        CHUNK["Split text into chunks<br/>200 words, 40-word overlap"]
        EMBED["OpenAI embeddings<br/>text-embedding-3-small<br/>1536 dimensions, batches of 32"]
        UPSERT["Upsert vectors and chunk metadata<br/>Namespace selected by document owner"]
        S3 --> READ --> CHUNK --> EMBED --> UPSERT
    end

    PC[("Pinecone vector index<br/>Cosine similarity<br/>Namespaces: hr / finance / it")]
    UPSERT --> PC

    subgraph CHAT[Conversation - app/services/]
        USER["User question<br/>user_id and optional session_id"]
        LOAD["Create or validate session<br/>Load conversation history"]
        DB[("AWS DynamoDB<br/>Session ownership, turn history,<br/>revision checks and expiry")]
        SAVE["Save completed question and response"]
        OUT["Return session_id, message and status"]
        USER --> LOAD
        DB -->|history| LOAD
        LOAD -->|create session when needed| DB
        SAVE --> DB
        SAVE --> OUT
    end

    subgraph RET[Retrieval - LangGraph]
        INTENT["Detect intent with LLM<br/>Select HR, FINANCE, IT_SUPPORT<br/>or multiple domains"]
        ROUTE{"Domains resolved?"}
        REWRITE["Rewrite query with LLM<br/>Use history and selected domains"]
        CLEAR{"Query clear?"}
        QEMBED["Embed standalone query<br/>text-embedding-3-small, 1536 dimensions"]
        SEARCH["Search selected Pinecone namespaces<br/>Top 5 per namespace; merge by score"]
        REL["LLM relevance evaluation<br/>Select useful chunks"]
        RESP["Respond<br/>Grounded LLM answer with source references,<br/>clarification, or no-answer message"]
        INTENT --> ROUTE
        ROUTE -->|Yes| REWRITE
        ROUTE -->|Unknown or needs clarification| RESP
        REWRITE --> CLEAR
        CLEAR -->|Yes| QEMBED
        CLEAR -->|Needs clarification| RESP
        QEMBED --> SEARCH --> REL --> RESP
    end

    LOAD -->|question and history| INTENT
    PC -->|candidate chunks and metadata| SEARCH
    RESP --> SAVE

    classDef storage fill:#e0f2fe,stroke:#0284c7,color:#0f172a;
    classDef model fill:#ede9fe,stroke:#7c3aed,color:#0f172a;
    class PC,DB,S3 storage;
    class EMBED,INTENT,REWRITE,QEMBED,REL,RESP model;
```

## Implementation details

- **Ingestion:** `injection/ingest.py` reads S3 `.txt` files and parses document
  headers. Each vector stores chunk text, document ID, title, version, effective
  date, owner and audience. Vector IDs combine a hash of the bucket/key with the
  chunk number.
- **Domain mapping:** Human Resources maps to `hr`, Finance to `finance`, and
  IT Support to `it`. Retrieval searches only the selected domains.
- **Shared embeddings:** Both flows use `text-embedding-3-small` with 1536
  dimensions. Ingestion validates a ready Pinecone index with cosine similarity.
- **Conversation:** `app/services/chat.py` loads history before invoking the
  graph and saves the completed exchange before returning. DynamoDB memory
  defaults to 10 prior turns and seven days of retention.
- **Response paths:** Intent detection and query rewriting can request
  clarification. No relevant chunks produce a no-answer message; useful chunks
  are supplied to the answer model with numbered document references.
- **Pending fallback:** `retrieval/core/graph.py` defines a query-repair loop
  with up to three retries, but `retrieval/nodes/fallback.py` raises
  `NotImplementedError`. The chat service explicitly disables this loop, so it
  is omitted from the active flow above. Direct `build_graph()` calls enable
  fallback by default and may reach that unfinished node.

## Main source files

| Responsibility | Source |
| --- | --- |
| S3 ingestion and Pinecone upload | [ingest.py](../injection/ingest.py) |
| Chunking and document embeddings | [chunking.py](../injection/chunking.py), [embedding.py](../injection/embedding.py) |
| Graph and conditional routing | [graph.py](../retrieval/core/graph.py), [router.py](../retrieval/core/router.py) |
| Retrieval nodes | [nodes/](../retrieval/nodes/) |
| Query embeddings and vector search | [embeddings.py](../retrieval/services/embeddings.py), [vector_store.py](../retrieval/services/vector_store.py) |
| Chat and conversation history | [chat.py](../app/services/chat.py), [conversation_memory.py](../app/services/conversation_memory.py) |

GitHub renders the Mermaid diagram when viewing this Markdown file.
