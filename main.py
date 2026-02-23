from fastapi import FastAPI, Request, Header, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from qdrant_client import QdrantClient, models
from openai import OpenAI
from dotenv import load_dotenv
import os

app = FastAPI(title="Qdrant Overwrite")

# Use absolute paths for reliability
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

load_dotenv()

qdrant_client = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    api_key=os.getenv("QDRANT_API_KEY")
)

COLLECTION_NAME = "HomeAlong Backend Run 5"

# Ensure the payload index exists
try:
    print(f"Ensuring payload index for {COLLECTION_NAME}...")
    qdrant_client.create_payload_index(
        collection_name=COLLECTION_NAME,
        field_name="metadata.original_file_name",
        field_schema=models.PayloadSchemaType.KEYWORD,
    )
    print("Payload index check/creation triggered.")
except Exception as e:
    print(f"Index creation note (this is usually fine if it already exists): {e}")

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],
)

class UpsertRequest(BaseModel):
    point_id: str
    file_name: str
    new_content: str
    action: str = "overwrite"

@app.get("/")
@app.get("/index.html")
async def read_index():
    print("Serving index.html")
    return FileResponse(os.path.join(BASE_DIR, "index.html"))

@app.get("/script.js")
async def read_script():
    print("Serving script.js")
    return FileResponse(os.path.join(BASE_DIR, "script.js"))

@app.get("/get_all_filenames")
async def get_all_filenames():
    print("Fetching all filenames...")
    try:
        all_filenames = set()
        next_page_offset = None
        while True:
            points, next_page_offset = qdrant_client.scroll(
                collection_name=COLLECTION_NAME,
                limit=100,
                with_payload=["metadata.original_file_name"],
                with_vectors=False,
                offset=next_page_offset
            )
            for point in points:
                name = point.payload.get("metadata", {}).get("original_file_name")
                if name:
                    all_filenames.add(name)
            if next_page_offset is None:
                break
        return {"filenames": list(all_filenames), "total_count": len(all_filenames)}
    except Exception as e:
        print(f"Error in get_all_filenames: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/scroll")
async def get_file_details(file_name: str):
    print(f"Scrolling chunks for file: {file_name}")
    try:
        points, next_page_offset = qdrant_client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="metadata.original_file_name",
                        match=models.MatchValue(value=file_name),
                    )
                ]
            ),
            limit=50,
            with_payload=True,
            with_vectors=False,
        )
        cleaned_results = []
        for p in points:
            cleaned_results.append({
                "id": p.id,
                "content": p.payload.get("content"),
                "filename": p.payload.get("metadata", {}).get("original_file_name")
            })
        return {"results": cleaned_results, "next_page_offset": next_page_offset}
    except Exception as e:
        print(f"Error accessing Qdrant: {e}")
        # If the index is missing, try creating it again (fallback)
        if "Index required but not found" in str(e):
             qdrant_client.create_payload_index(
                collection_name=COLLECTION_NAME,
                field_name="metadata.original_file_name",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upsert")
async def overwrite_file_details(req: UpsertRequest):
    print(f"Upserting chunk {req.point_id} for file {req.file_name}")
    try:
        # Try to use integer ID if possible, fallback to string (UUID)
        try:
            target_id = int(req.point_id)
        except ValueError:
            target_id = req.point_id

        points = qdrant_client.retrieve(
            collection_name=COLLECTION_NAME,
            ids=[target_id],
            with_payload=True
        )
        if not points:
            raise HTTPException(status_code=404, detail=f"Point ID {req.point_id} not found.")

        existing_point = points[0]
        payload = existing_point.payload
        metadata = payload.get("metadata", {})
        
        actual_filename = metadata.get("original_file_name")
        if actual_filename != req.file_name:
            raise HTTPException(status_code=400, detail=f"Safety Mismatch: Point ID {req.point_id} belongs to '{actual_filename}'.")

        final_content = req.new_content
        if req.action == "append":
            old_content = payload.get("content", "")
            final_content = f"{old_content}\n{req.new_content}"

        print("Generating embedding...")
        response = openai_client.embeddings.create(input=final_content, model="text-embedding-3-large")
        new_vector = response.data[0].embedding

        qdrant_client.upsert(
            collection_name=COLLECTION_NAME,
            points=[models.PointStruct(id=target_id, vector=new_vector, payload={**payload, "content": final_content})]
        )
        return {"status": "success", "message": f"Updated {req.point_id}"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in upsert: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting FastAPI server on http://localhost:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)