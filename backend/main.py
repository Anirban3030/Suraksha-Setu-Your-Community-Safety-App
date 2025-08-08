from fastapi import FastAPI
from backend.router import router
from fastapi.middleware.cors import CORSMiddleware
app = FastAPI()

#Adding CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Add the router that handles /report endpoint
app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)


