from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form
from sqlalchemy.orm import Session
from typing import List, Optional
import shutil, os

from dependencias import pegar_sessao, verificar_token, verificar_admin
from schemas import (
    ProdutoSchema, ResponseProdutoSchema, ResponseProdutoDetalhadoSchema,
    VariacaoSchema, ResponseVariacaoSchema,
)
from models import Produto, Categoria, Porcao, VariacaoProduto, Usuario

product_router = APIRouter(prefix="/Produto", tags=["Produtos"])

PASTA_IMAGENS = "static/produtos"


def _get_produto(produto_id: int, session: Session) -> Produto:
    p = session.query(Produto).filter(Produto.id == produto_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    return p


# ============================================================
# PRODUTOS — CRUD
# ============================================================

@product_router.get(
    "/produtos",
    response_model=List[ResponseProdutoDetalhadoSchema],
    summary="Lista todos os produtos (com filtros opcionais)"
)
async def listar_produtos(
    categoria_id: Optional[int]  = None,
    disponivel:   Optional[bool] = None,
    session:      Session        = Depends(pegar_sessao),
):
    q = session.query(Produto)
    if categoria_id is not None:
        q = q.filter(Produto.categoria_id == categoria_id)
    if disponivel is not None:
        q = q.filter(Produto.disponivel == disponivel)
    return q.all()


@product_router.get(
    "/produtos/{produto_id}",
    response_model=ResponseProdutoDetalhadoSchema,
    summary="Busca um produto pelo ID"
)
async def buscar_produto(produto_id: int, session: Session = Depends(pegar_sessao)):
    return _get_produto(produto_id, session)


@product_router.post(
    "/produtos",
    response_model=ResponseProdutoSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Cria produto via JSON (somente admin). porcao_id é opcional."
)
async def criar_produto(
    dados:   ProdutoSchema,
    session: Session = Depends(pegar_sessao),
    _:       Usuario = Depends(verificar_admin),
):
    # Categoria é obrigatória
    if not session.query(Categoria).filter(Categoria.id == dados.categoria_id).first():
        raise HTTPException(status_code=404, detail="Categoria não encontrada")

    # Porção é OPCIONAL — só valida se o admin enviou porcao_id
    if dados.porcao_id is not None:
        if not session.query(Porcao).filter(Porcao.id == dados.porcao_id).first():
            raise HTTPException(status_code=404, detail="Porção não encontrada")

    produto = Produto(
        nome=dados.nome,
        descricao=dados.descricao,
        preco=dados.preco,
        categoria_id=dados.categoria_id,
        porcao_id=dados.porcao_id,           # None se não enviado
        disponivel=dados.disponivel if dados.disponivel is not None else True,
    )
    session.add(produto)
    try:
        session.commit()
        session.refresh(produto)
    except Exception:
        session.rollback()
        raise HTTPException(status_code=400, detail="Já existe um produto com esse nome")
    return produto


@product_router.post(
    "/produtos/com-foto",
    response_model=ResponseProdutoSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Cria produto com imagem via multipart/form-data (somente admin)"
)
async def criar_produto_com_foto(
    nome:         str           = Form(...),
    preco:        float         = Form(...),
    categoria_id: int           = Form(...),
    descricao:    Optional[str] = Form(None),
    porcao_id:    Optional[int] = Form(None),   # opcional
    disponivel:   bool          = Form(True),
    imagem:       UploadFile    = File(...),
    session:      Session       = Depends(pegar_sessao),
    _:            Usuario       = Depends(verificar_admin),
):
    if not session.query(Categoria).filter(Categoria.id == categoria_id).first():
        raise HTTPException(status_code=404, detail="Categoria não encontrada")

    if porcao_id is not None:
        if not session.query(Porcao).filter(Porcao.id == porcao_id).first():
            raise HTTPException(status_code=404, detail="Porção não encontrada")

    os.makedirs(PASTA_IMAGENS, exist_ok=True)
    caminho = f"{PASTA_IMAGENS}/{imagem.filename}"
    try:
        with open(caminho, "wb") as f:
            shutil.copyfileobj(imagem.file, f)
    except Exception:
        raise HTTPException(status_code=500, detail="Erro ao salvar imagem")

    produto = Produto(
        nome=nome, preco=preco, descricao=descricao,
        categoria_id=categoria_id, porcao_id=porcao_id,
        disponivel=disponivel, imagem_url=caminho,
    )
    session.add(produto)
    try:
        session.commit()
        session.refresh(produto)
    except Exception:
        session.rollback()
        raise HTTPException(status_code=400, detail="Já existe um produto com esse nome")
    return produto


@product_router.put(
    "/produtos/{produto_id}",
    response_model=ResponseProdutoSchema,
    summary="Edita um produto (somente admin)"
)
async def editar_produto(
    produto_id: int,
    dados:   ProdutoSchema,
    session: Session = Depends(pegar_sessao),
    _:       Usuario = Depends(verificar_admin),
):
    produto = _get_produto(produto_id, session)

    if not session.query(Categoria).filter(Categoria.id == dados.categoria_id).first():
        raise HTTPException(status_code=404, detail="Categoria não encontrada")
    produto.categoria_id = dados.categoria_id

    # Porção: se enviou None, remove; se enviou um id, valida e atualiza
    if dados.porcao_id is not None:
        if not session.query(Porcao).filter(Porcao.id == dados.porcao_id).first():
            raise HTTPException(status_code=404, detail="Porção não encontrada")
    produto.porcao_id = dados.porcao_id   # pode virar None para remover a porção

    produto.nome      = dados.nome
    produto.descricao = dados.descricao
    produto.preco     = dados.preco
    if dados.disponivel is not None:
        produto.disponivel = dados.disponivel

    session.commit()
    session.refresh(produto)
    return produto


@product_router.patch(
    "/produtos/{produto_id}/disponibilidade",
    summary="Ativa ou desativa um produto (somente admin)"
)
async def alterar_disponibilidade(
    produto_id: int,
    disponivel: bool,
    session: Session = Depends(pegar_sessao),
    _: Usuario = Depends(verificar_admin),
):
    produto = _get_produto(produto_id, session)
    produto.disponivel = disponivel
    session.commit()
    return {"mensagem": f"Produto '{produto.nome}' marcado como {'disponível' if disponivel else 'indisponível'}"}


@product_router.delete(
    "/produtos/deletar/{produto_id}",
    summary="Remove um produto (somente admin)"
)
async def deletar_produto(
    produto_id: int,
    session: Session = Depends(pegar_sessao),
    _: Usuario = Depends(verificar_admin),
):
    produto = _get_produto(produto_id, session)
    session.delete(produto)
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise HTTPException(status_code=400, detail="Não é possível deletar produto vinculado a pedidos")
    return {"mensagem": f"Produto '{produto.nome}' removido com sucesso"}


# ============================================================
# VARIAÇÕES DE PRODUTO
# Rota: /Produto/produtos/{produto_id}/variacoes
#
# Use para cadastrar: House Simples, House Pro, House Pro Max
# Cada variação tem um acréscimo sobre o preço base do produto.
# ============================================================

@product_router.get(
    "/produtos/{produto_id}/variacoes",
    response_model=List[ResponseVariacaoSchema],
    summary="Lista todas as variações de um produto"
)
async def listar_variacoes(produto_id: int, session: Session = Depends(pegar_sessao)):
    _get_produto(produto_id, session)
    return session.query(VariacaoProduto).filter(VariacaoProduto.produto_id == produto_id).all()


@product_router.post(
    "/produtos/{produto_id}/variacoes",
    response_model=ResponseVariacaoSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Adiciona uma variação ao produto (somente admin)"
)
async def criar_variacao(
    produto_id: int,
    dados:   VariacaoSchema,
    session: Session = Depends(pegar_sessao),
    _:       Usuario = Depends(verificar_admin),
):
    produto = _get_produto(produto_id, session)
    variacao = VariacaoProduto(
        nome=dados.nome,
        descricao=dados.descricao,
        acrescimo=dados.acrescimo,
        disponivel=dados.disponivel if dados.disponivel is not None else True,
        produto_id=produto.id,
    )
    session.add(variacao)
    session.commit()
    session.refresh(variacao)
    return variacao


@product_router.put(
    "/produtos/{produto_id}/variacoes/{variacao_id}",
    response_model=ResponseVariacaoSchema,
    summary="Edita uma variação (somente admin)"
)
async def editar_variacao(
    produto_id:  int,
    variacao_id: int,
    dados:   VariacaoSchema,
    session: Session = Depends(pegar_sessao),
    _:       Usuario = Depends(verificar_admin),
):
    _get_produto(produto_id, session)
    variacao = session.query(VariacaoProduto).filter(
        VariacaoProduto.id == variacao_id,
        VariacaoProduto.produto_id == produto_id,
    ).first()
    if not variacao:
        raise HTTPException(status_code=404, detail="Variação não encontrada")

    variacao.nome      = dados.nome
    variacao.descricao = dados.descricao
    variacao.acrescimo = dados.acrescimo
    if dados.disponivel is not None:
        variacao.disponivel = dados.disponivel

    session.commit()
    session.refresh(variacao)
    return variacao


@product_router.patch(
    "/produtos/{produto_id}/variacoes/{variacao_id}/disponibilidade",
    summary="Ativa ou desativa uma variação (somente admin)"
)
async def alterar_disponibilidade_variacao(
    produto_id:  int,
    variacao_id: int,
    disponivel:  bool,
    session: Session = Depends(pegar_sessao),
    _: Usuario = Depends(verificar_admin),
):
    _get_produto(produto_id, session)
    variacao = session.query(VariacaoProduto).filter(
        VariacaoProduto.id == variacao_id,
        VariacaoProduto.produto_id == produto_id,
    ).first()
    if not variacao:
        raise HTTPException(status_code=404, detail="Variação não encontrada")
    variacao.disponivel = disponivel
    session.commit()
    return {"mensagem": f"Variação '{variacao.nome}' marcada como {'disponível' if disponivel else 'indisponível'}"}


@product_router.delete(
    "/produtos/{produto_id}/variacoes/{variacao_id}",
    summary="Remove uma variação (somente admin)"
)
async def deletar_variacao(
    produto_id:  int,
    variacao_id: int,
    session: Session = Depends(pegar_sessao),
    _: Usuario = Depends(verificar_admin),
):
    _get_produto(produto_id, session)
    variacao = session.query(VariacaoProduto).filter(
        VariacaoProduto.id == variacao_id,
        VariacaoProduto.produto_id == produto_id,
    ).first()
    if not variacao:
        raise HTTPException(status_code=404, detail="Variação não encontrada")
    session.delete(variacao)
    session.commit()
    return {"mensagem": f"Variação '{variacao.nome}' removida com sucesso"}