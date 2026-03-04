This project implements a NotebookLM like Google's NotebookLM. It uses a Retrieval Augmented Generation (RAG)
architecture. The goal of the system is to allow userrs to upload documents into notebooks, ask question about said documents,
and generate artifacts such as summaries, quizzes, and podcast transcripts based on the notebook content. The system is designed to 
mimic the workflow of tools that Google NotebookLM has, where users are able to organize sources into notebooks and interact with the 
sources through an AI interface that provides answers with sources/citations. 

The system is built modular, that seperates user interface, backend logic, and storage layers. The frontend is implemented using 
Gradio, which provides an interactive web interface for managing the notebook, source ingestion, question answering, and artifact 
generation. Users can create notebooks, upload .txt, .pdf, .pptx, and URLs, toggle sources on or off, and interact with the system 
through a chat interface. The interface also lets users generate artifacts such as reports, quizzes, and podcast transcripts, which
can then be downloaded directly onto the users computer. 

The backend consists of several core modules, responsible for ingestion, chunking, retrieval, and artifact generation.
the ingestion pipeline processes input docuemnts and gets them ready for retrieval. The system supports multiple document formats 
as said earlier, such as PDF, PPTX, TXT, and more specifically, single page URL's. During ingestion, documents are first copied into 
a raw storage directory, and then processed by an extraction module that converts the document into plain text. After extraction, 
the text is chunked, using a sliding window chunking strategy. In this implementation, chunks are 1100 characters in length with 
a 180 character overlap between adjacent chunks. This overlap helps preserve context across chunk boundaries and improve our 
retrieval quality. 

Each chunk is embedded using a sentecne transformer embedding model. These embeddings represent each chunk as a vector. The vectors
are stored in a Chroma vector database along with metadata such as source document ID, and the chunk location within the document.
Storing the metadata allows the system to generate citations that reference the original document and chunk location when answering
question. The vector database is persisted within each notebook's directory, allowing retrieval to operate only on soruces belonging to
the selected notebook.

When a user asks a question through the chatr interface, the system will execute the retrieval pipeline. The user's query is 
embedded using the same embedding model as stated earlier, and a similarity search is performed against the vector database to retrieve
the most relevant chunks. This system retrieves the top-k chunks (usually around 5 to 6) that have the highest semantic similarity to 
the query. These chunks are then formatted as context snippets and inserted into a prompt that is sent to the language model. the 
prompt has strict instructions telling the model to answer using only the provided context and to avoid hallucinating information
that does not appear in the sources. This grounding strategy helps reduce inventing information/hallucinations, and ensures the 
responses are related and useful to the notebooks content.

The language model I used for generation is through using GROQ API. The retrieved context snippets and the user questions are combined 
into a structued prompt, that the model generates an answer that references the retrieved soruces. The system then formats the response
with citations that point back to the original document chunks. Then the citations will appear as numbered references that indicate
to the user which sources were used to generate the answer. This makes it easy for users to trace the information back to its original
context so they can verify the responses.

In addition to answering questions, the system can also generate several types of artifacts from the notebook content. These include 
structed reports, quizzes with answer keys, and podcast-style transcripts. Artifact generation works by retrieving relevant chunksfrom the 
vector database and passing them to the language model with prompts designed for each artifact type. For example, report generation produces
a structed summary of the notebook's content, quiz generation produces questions along with the answers, and podcast generation produces
a conversational transcript designed to resemble a real life podcast discussion about the material. These artifacts are saved within the 
notebook's artifact directory and are available for download through the Gradio interface.

The system also includes a storage layer signed to support multi-user isolation and notebook organization. Each user has a dedicated 
directory where their notebooks and data are stored. Within each notebook directory, the system stores raw uploaded files, 
extracted text versions of the files, the vector database used for retrieval, and finally, any generated artifacts. This structure ensures 
that each notebook is able to operate independently, and that users cannot access data belonging to other users. The storage layout 
also makes it easier to maintain persistence for when the application restarts and supports the ability to manage multiple notebooks
per user.

This desing emphasizes modularity and seperation of concerns. Our ingestion pipeline is responsible for document processing adn embedding
generation, the retrieval module handles vector seearch and context assembly, the artifact module manages artifact creation, and the user 
interface layer can coordinate interactions between the user and trhe backend components. This modular appraoch has system maintainence and 
scalability in mind. Since individual components can be modified or replaced without affecting the entire application.

Several design tradeoffs were considered while developing this project. A lightweight, embedding model was chosen so we could balance
performance and computational cost. While when we implemented larger embedding models, the latency and resource requirements went up, but
we had better retrieval accuracy. Chunk size and overlap values wer also selected so we could balance context coverage with efficient retrieval.
Larger chunks can provide more context but can also reduce retrieval precision, while smaller chunks can improve precision, but can miss out 
on important information. Our final model is a compromise between all of these factors. 

Overall, the system demonstrates how a Retrieval AUgmented Generation architecture can be used to build an interactive study assistant
capable of grounding answers in user provided documents. By combining document ingestion, vectory search, and language model reasoning,
the system lets users to explore and analyze thier sources though natural language queries while maintaining clarity through citations.
The modular architecture, structed storage system, and artifact generation capabilities all came together to create a workflow
that resemembles a Google's NotebookLM.
