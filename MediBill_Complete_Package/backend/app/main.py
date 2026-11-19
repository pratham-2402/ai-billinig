from __future__ import annotations
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

import jwt
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pwdlib import PasswordHash
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker, Session

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./medibill_dev.db")
JWT_SECRET = os.getenv("JWT_SECRET", "development-only-change-me")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "ChangeThisAdminPassword123!")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
password_hash = PasswordHash.recommended()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

class Base(DeclarativeBase): pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class Medicine(Base):
    __tablename__ = "medicines"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    batch: Mapped[str] = mapped_column(String(80), default="")
    expiry: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    mrp: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    stock: Mapped[int] = mapped_column(Integer, default=0)
    barcode: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

class Sale(Base):
    __tablename__ = "sales"
    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_no: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    customer_name: Mapped[str] = mapped_column(String(160), default="Walk-in customer")
    payment_method: Mapped[str] = mapped_column(String(20))
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    items: Mapped[list["SaleItem"]] = relationship(back_populates="sale", cascade="all, delete-orphan")

class SaleItem(Base):
    __tablename__ = "sale_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.id"))
    medicine_id: Mapped[int] = mapped_column(ForeignKey("medicines.id"))
    medicine_name: Mapped[str] = mapped_column(String(200))
    batch: Mapped[str] = mapped_column(String(80), default="")
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    sale: Mapped[Sale] = relationship(back_populates="items")

class MedicineIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    batch: str = Field(default="", max_length=80)
    expiry: Optional[str] = None
    mrp: Decimal = Field(ge=0)
    stock: int = Field(ge=0)
    barcode: Optional[str] = None
    is_demo: bool = False

class MedicineOut(MedicineIn):
    id: int
    model_config = {"from_attributes": True}

class SaleLineIn(BaseModel):
    medicine_id: int
    quantity: int = Field(gt=0)

class SaleIn(BaseModel):
    invoice_no: str = Field(min_length=1, max_length=40)
    customer_name: str = "Walk-in customer"
    payment_method: str = Field(pattern="^(Cash|UPI|Card)$")
    discount_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    items: list[SaleLineIn] = Field(min_length=1)

class SaleOut(BaseModel):
    id: int
    invoice_no: str
    customer_name: str
    payment_method: str
    total: Decimal
    created_at: datetime
    model_config = {"from_attributes": True}

app = FastAPI(title="MediBill API", version="0.2.0", description="Development API foundation for Amruta Medicals And General Stores")

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.username == ADMIN_USERNAME)) is None:
            db.add(User(username=ADMIN_USERNAME, password_hash=password_hash.hash(ADMIN_PASSWORD)))
            db.commit()

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

def current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        username = payload.get("sub")
        if not username: raise ValueError("Missing subject")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired access token", headers={"WWW-Authenticate": "Bearer"})
    user = db.scalar(select(User).where(User.username == username, User.is_active.is_(True)))
    if not user: raise HTTPException(status_code=401, detail="Inactive or unknown user")
    return user

@app.get("/health")
def health():
    return {"status": "ok", "service": "medibill-api", "version": "0.2.0"}

@app.get("/store")
def store_profile(_: User = Depends(current_user)):
    """Return the configured pharmacy profile; blank fields stay blank until supplied."""
    return {
        "name": os.getenv("STORE_NAME", "Amruta Medicals And General Stores"),
        "phone": os.getenv("STORE_PHONE", "9901544875"),
        "email": os.getenv("STORE_EMAIL", ""),
        "address": os.getenv("STORE_ADDRESS", ""),
        "drug_licence": os.getenv("DRUG_LICENCE", ""),
        "currency": "INR",
        "gst_registered": os.getenv("GST_REGISTERED", "false").lower() == "true",
    }

@app.get("/inventory/summary")
def inventory_summary(_: User = Depends(current_user), db: Session = Depends(get_db)):
    """Basic stock totals. Demo records are reported separately, never hidden."""
    records = list(db.scalars(select(Medicine)).all())
    real_records = [m for m in records if not m.is_demo]
    return {
        "medicine_records": len(records),
        "demo_records": sum(1 for m in records if m.is_demo),
        "verified_records": len(real_records),
        "units_in_stock": sum(m.stock for m in real_records),
        "low_stock_records": sum(1 for m in real_records if m.stock <= 10),
    }

@app.post("/auth/token")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == form.username))
    if not user or not user.is_active or not password_hash.verify(form.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
    now = datetime.now(timezone.utc)
    token = jwt.encode({"sub": user.username, "iat": now, "exp": now + timedelta(minutes=JWT_EXPIRE_MINUTES)}, JWT_SECRET, algorithm="HS256")
    return {"access_token": token, "token_type": "bearer", "expires_in": JWT_EXPIRE_MINUTES * 60}

@app.get("/medicines", response_model=list[MedicineOut])
def list_medicines(_: User = Depends(current_user), db: Session = Depends(get_db)):
    return list(db.scalars(select(Medicine).order_by(Medicine.name)).all())

@app.post("/medicines", response_model=MedicineOut, status_code=201)
def add_medicine(payload: MedicineIn, _: User = Depends(current_user), db: Session = Depends(get_db)):
    med = Medicine(**payload.model_dump())
    db.add(med); db.commit(); db.refresh(med)
    return med

@app.post("/sales", response_model=SaleOut, status_code=201)
def create_sale(payload: SaleIn, _: User = Depends(current_user), db: Session = Depends(get_db)):
    if db.scalar(select(Sale).where(Sale.invoice_no == payload.invoice_no)):
        raise HTTPException(status_code=409, detail="Invoice number already exists")
    try:
        lines = []
        subtotal = Decimal("0.00")
        # A single DB transaction ensures stock is not deducted if any line fails.
        for line in payload.items:
            med = db.scalar(select(Medicine).where(Medicine.id == line.medicine_id).with_for_update())
            if med is None: raise HTTPException(status_code=404, detail=f"Medicine {line.medicine_id} not found")
            if med.is_demo: raise HTTPException(status_code=400, detail=f"{med.name} is demo stock; replace it before sale")
            if med.expiry and med.expiry < datetime.now().strftime("%Y-%m"):
                raise HTTPException(status_code=400, detail=f"{med.name} batch is expired")
            if med.stock < line.quantity: raise HTTPException(status_code=400, detail=f"Insufficient stock for {med.name}")
            amount = Decimal(med.mrp) * line.quantity
            subtotal += amount
            lines.append((med, line.quantity, amount))
        total = (subtotal * (Decimal("100") - payload.discount_percent) / Decimal("100")).quantize(Decimal("0.01"))
        sale = Sale(invoice_no=payload.invoice_no, customer_name=payload.customer_name, payment_method=payload.payment_method, total=total)
        for med, qty, amount in lines:
            med.stock -= qty
            sale.items.append(SaleItem(medicine_id=med.id, medicine_name=med.name, batch=med.batch, quantity=qty, unit_price=med.mrp))
        db.add(sale); db.commit(); db.refresh(sale)
        return sale
    except Exception:
        db.rollback()
        raise

@app.get("/sales", response_model=list[SaleOut])
def list_sales(_: User = Depends(current_user), db: Session = Depends(get_db)):
    return list(db.scalars(select(Sale).order_by(Sale.created_at.desc())).all())
