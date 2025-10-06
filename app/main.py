from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from .database import engine, get_session
from .models import SQLModel, Link
from .schemas import LinkCreate, LinkOut
from .crud import create_link
import datetime

app = FastAPI(title="QuickPath")

templates = Jinja2Templates(directory="app/templates")

@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

# Crée toutes les tables au lancement (simple pour SQLite)
SQLModel.metadata.create_all(bind=engine)

@app.post("/links", response_model=LinkOut, status_code=status.HTTP_201_CREATED)
def shorten_link(payload: LinkCreate, session: Session = Depends(get_session)):
    link = create_link(session, str(payload.url), payload.expires_at)
    return {
        "slug": link.slug,
        "short_url": f"{app.url_path_for('redirect', slug=link.slug)}"
    }

@app.get("/links/{slug}")
def get_stats(slug: str, session: Session = Depends(get_session)):
    link: Link | None = session.exec(select(Link).where(Link.slug == slug)).first()
    if not link:
        raise HTTPException(status_code=404, detail="Lien introuvable")

    return {
        "clicks": link.clicks,
        "created_at": link.created_at,
        "last_accessed": link.last_accessed,
        "expires_at": link.expires_at,
    }

@app.get("/{slug}", name="redirect")
def redirect(slug: str, session: Session = Depends(get_session)):
    link: Link | None = session.exec(select(Link).where(Link.slug == slug)).first()
    if not link:
        raise HTTPException(status_code=404, detail="Lien introuvable")
    if link.expires_at and link.expires_at < datetime.datetime.utcnow():
        raise HTTPException(status_code=410, detail="Lien expiré")
    link.clicks += 1
    link.last_accessed = datetime.datetime.utcnow()
    session.add(link)
    session.commit()
    return RedirectResponse(link.original_url, status_code=301)
