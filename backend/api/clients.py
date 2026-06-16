from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from typing import Optional, List
from datetime import date

from database import get_db
from api.auth import get_current_user
from models import User, Client, ClientType

router = APIRouter()


class CreateClientRequest(BaseModel):
    full_name: str
    pan: str
    client_type: ClientType = ClientType.INDIVIDUAL
    email: Optional[str] = None
    phone: Optional[str] = None
    gstin: Optional[str] = None
    tan: Optional[str] = None
    dob: Optional[date] = None
    state_code: Optional[str] = None
    is_tds_deductor: bool = False
    gst_registered: bool = False
    tags: List[str] = []
    internal_notes: Optional[str] = None


class UpdateClientRequest(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    gstin: Optional[str] = None
    tan: Optional[str] = None
    itr_form_type: Optional[str] = None
    tags: Optional[List[str]] = None
    internal_notes: Optional[str] = None
    is_active: Optional[bool] = None


@router.post("", status_code=201)
async def create_client(
    req: CreateClientRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Check duplicate PAN under this CA
    result = await db.execute(
        select(Client).where(
            Client.pan == req.pan.upper(),
            Client.owner_id == current_user.id,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Client with PAN {req.pan} already exists")

    client = Client(
        owner_id=current_user.id,
        full_name=req.full_name,
        pan=req.pan.upper(),
        client_type=req.client_type,
        email=req.email,
        phone=req.phone,
        gstin=req.gstin.upper() if req.gstin else None,
        tan=req.tan.upper() if req.tan else None,
        dob=req.dob,
        state_code=req.state_code,
        is_tds_deductor=req.is_tds_deductor,
        gst_registered=req.gst_registered,
        tags=req.tags,
        internal_notes=req.internal_notes,
    )
    db.add(client)
    await db.flush()
    return {"id": str(client.id), "message": "Client created", "pan": client.pan}


@router.get("")
async def list_clients(
    search: Optional[str] = Query(None),
    client_type: Optional[ClientType] = None,
    is_active: bool = True,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Client).where(
        Client.owner_id == current_user.id,
        Client.is_active == is_active,
    )

    if search:
        query = query.where(
            (Client.full_name.ilike(f"%{search}%")) |
            (Client.pan.ilike(f"%{search}%")) |
            (Client.gstin.ilike(f"%{search}%"))
        )

    if client_type:
        query = query.where(Client.client_type == client_type)

    # Total count
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar()

    # Paginated results
    query = query.offset((page - 1) * per_page).limit(per_page).order_by(Client.full_name)
    result = await db.execute(query)
    clients = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "clients": [
            {
                "id": str(c.id),
                "full_name": c.full_name,
                "pan": c.pan,
                "gstin": c.gstin,
                "tan": c.tan,
                "client_type": c.client_type.value,
                "gst_registered": c.gst_registered,
                "is_tds_deductor": c.is_tds_deductor,
                "tags": c.tags,
                "current_fy": c.current_fy,
                "itr_form_type": c.itr_form_type,
            }
            for c in clients
        ]
    }


@router.get("/{client_id}")
async def get_client(
    client_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Client).where(Client.id == client_id, Client.owner_id == current_user.id)
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    return {
        "id": str(client.id),
        "full_name": client.full_name,
        "pan": client.pan,
        "gstin": client.gstin,
        "tan": client.tan,
        "email": client.email,
        "phone": client.phone,
        "client_type": client.client_type.value,
        "gst_registered": client.gst_registered,
        "is_tds_deductor": client.is_tds_deductor,
        "dob": client.dob,
        "state_code": client.state_code,
        "tags": client.tags,
        "internal_notes": client.internal_notes,
        "current_fy": client.current_fy,
        "itr_form_type": client.itr_form_type,
        "auto_fetch_enabled": client.auto_fetch_enabled,
        "created_at": client.created_at,
    }


@router.patch("/{client_id}")
async def update_client(
    client_id: str,
    req: UpdateClientRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Client).where(Client.id == client_id, Client.owner_id == current_user.id)
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    for field, value in req.model_dump(exclude_none=True).items():
        setattr(client, field, value)

    return {"message": "Client updated"}


@router.delete("/{client_id}")
async def delete_client(
    client_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Client).where(Client.id == client_id, Client.owner_id == current_user.id)
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    client.is_active = False   # Soft delete
    return {"message": "Client deactivated"}
