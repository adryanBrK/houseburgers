import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import sessionmaker

from models import Base, db, Usuario
from auth_routes    import auth_router
from product_routes import product_router
from order_routes   import order_router
from sales_routes   import sales_router
from store_routes   import store_router


def _inicializar():
    Base.metadata.create_all(bind=db)
    session = sessionmaker(bind=db)()
    try:
        if not session.query(Usuario).filter(Usuario.email == "admin@hamburgueria.com").first():
            session.add(Usuario(nome="Administrador", email="admin@hamburgueria.com",
                                senha="admin123", admin=True, ativo=True))
            session.commit()
            print("✅ Admin criado  →  admin@hamburgueria.com  /  admin123")
    finally:
        session.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _inicializar()
    yield


app = FastAPI(
    title="🍔 API Hamburgueria",
    description="API completa para delivery de hamburgueria",
    version="2.1.0",
    lifespan=lifespan,
)

# ─────────────────────────────────────────────────────────────────
# CORS — lista explícita dos domínios permitidos
# Adicione aqui qualquer outro domínio do seu front (Vercel, etc.)
# ─────────────────────────────────────────────────────────────────
ALLOWED_ORIGINS = [
    "https://house-burgers.vercel.app",   # front de produção
    "https://houseburger2.vercel.app",    # própria API (docs/swagger)
    "http://localhost",                   # dev local
    "http://localhost:3000",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("static/produtos", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth_router)
app.include_router(product_router)
app.include_router(order_router)
app.include_router(sales_router)
app.include_router(store_router)


@app.get("/", tags=["Status"])
def raiz():
    return {"status": "online", "docs": "/docs", "versao": "2.1.0"}

# uvicorn main:app --reload
