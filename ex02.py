import re
from datetime import date
from enum import Enum
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

app = FastAPI(title="IT Asset & Allocation Management API")

EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


class AssetStatus(str, Enum):
    READY = "READY"
    ALLOCATED = "ALLOCATED"
    REPAIRING = "REPAIRING"
    SCRAPPED = "SCRAPPED"


class AssetCreate(BaseModel):
    serial_number: str = Field(..., min_length=1)
    model: str = Field(..., min_length=2, max_length=255)
    stock_available: int = Field(..., ge=0)
    status: AssetStatus


class AssetUpdate(BaseModel):
    serial_number: str = Field(..., min_length=1)
    model: str = Field(..., min_length=2, max_length=255)
    stock_available: int = Field(..., ge=0)
    status: AssetStatus


class Asset(AssetCreate):
    id: int


class AllocationCreate(BaseModel):
    asset_id: int
    employee_email: str
    allocated_quantity: int = Field(..., gt=0)
    start_date: date
    duration_months: int = Field(..., ge=1, le=12)

    @field_validator("employee_email")
    @classmethod
    def validate_email_format(cls, value: str) -> str:
        if not EMAIL_PATTERN.match(value):
            raise ValueError("Invalid email format")
        return value


class Allocation(AllocationCreate):
    id: int


assets: list[Asset] = [
    Asset(id=1, serial_number="SN-MAC-01", model="MacBook Pro M3", stock_available=5, status=AssetStatus.READY),
    Asset(id=2, serial_number="SN-DELL-02", model="Dell UltraSharp 27", stock_available=10, status=AssetStatus.READY),
    Asset(id=3, serial_number="SN-THINK-03", model="ThinkPad X1 Carbon", stock_available=0, status=AssetStatus.REPAIRING),
]

allocations: list[Allocation] = [
    Allocation(
        id=1,
        asset_id=1,
        employee_email="dev.nguyen@company.com",
        allocated_quantity=1,
        start_date=date(2026, 7, 1),
        duration_months=12,
    )
]

next_asset_id = 4
next_allocation_id = 2


def find_asset(asset_id: int) -> Optional[Asset]:
    return next((a for a in assets if a.id == asset_id), None)


def get_asset_or_404(asset_id: int) -> Asset:
    asset = find_asset(asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


def is_serial_number_duplicate(serial_number: str, exclude_id: Optional[int] = None) -> bool:
    return any(
        a.serial_number.lower() == serial_number.lower() and a.id != exclude_id
        for a in assets
    )


@app.post("/assets", response_model=Asset, status_code=201)
def create_asset(payload: AssetCreate):
    global next_asset_id
    if is_serial_number_duplicate(payload.serial_number):
        raise HTTPException(status_code=400, detail="Serial number already exists")

    asset = Asset(id=next_asset_id, **payload.model_dump())
    assets.append(asset)
    next_asset_id += 1
    return asset


@app.get("/assets", response_model=list[Asset])
def list_assets(
    keyword: Optional[str] = Query(default=None),
    status: Optional[AssetStatus] = Query(default=None),
    min_stock: Optional[int] = Query(default=None, ge=0),
):
    result = assets

    if keyword:
        keyword_lower = keyword.lower()
        result = [
            a for a in result
            if keyword_lower in a.serial_number.lower() or keyword_lower in a.model.lower()
        ]

    if status:
        result = [a for a in result if a.status == status]

    if min_stock is not None:
        result = [a for a in result if a.stock_available >= min_stock]

    return result


@app.get("/assets/{asset_id}", response_model=Asset)
def get_asset(asset_id: int):
    return get_asset_or_404(asset_id)


@app.put("/assets/{asset_id}", response_model=Asset)
def update_asset(asset_id: int, payload: AssetUpdate):
    asset = get_asset_or_404(asset_id)

    if is_serial_number_duplicate(payload.serial_number, exclude_id=asset_id):
        raise HTTPException(status_code=400, detail="Serial number already exists")

    asset.serial_number = payload.serial_number
    asset.model = payload.model
    asset.stock_available = payload.stock_available
    asset.status = payload.status
    return asset


@app.delete("/assets/{asset_id}", status_code=204)
def delete_asset(asset_id: int):
    asset = get_asset_or_404(asset_id)
    assets.remove(asset)
    return None


@app.post("/allocations", response_model=Allocation, status_code=201)
def create_allocation(payload: AllocationCreate):
    global next_allocation_id

    asset = find_asset(payload.asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")

    if asset.status != AssetStatus.READY:
        raise HTTPException(status_code=400, detail="Asset is not ready for allocation")

    if payload.allocated_quantity > asset.stock_available:
        raise HTTPException(status_code=400, detail="Allocated quantity exceeds available stock")

    allocation = Allocation(id=next_allocation_id, **payload.model_dump())
    allocations.append(allocation)
    next_allocation_id += 1
    return allocation


@app.get("/allocations", response_model=list[Allocation])
def list_allocations():
    return allocations