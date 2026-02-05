
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import models, schemas
from database import get_db

router = APIRouter()

@router.get("", response_model=List[schemas.BranchResponse])
def list_branches(db: Session = Depends(get_db)):
    return db.query(models.Branch).all()

@router.post("", response_model=schemas.BranchResponse)
def create_branch(branch: schemas.BranchCreate, db: Session = Depends(get_db)):
    db_branch = models.Branch(**branch.dict())
    db.add(db_branch)
    db.commit()
    db.refresh(db_branch)
    return db_branch

@router.put("/{id}", response_model=schemas.BranchResponse)
def update_branch(id: int, branch: schemas.BranchCreate, db: Session = Depends(get_db)):
    db_branch = db.query(models.Branch).filter(models.Branch.id == id).first()
    if not db_branch: raise HTTPException(404)
    for k, v in branch.dict().items(): setattr(db_branch, k, v)
    db.commit()
    db.refresh(db_branch)
    return db_branch

@router.delete("/{id}")
def delete_branch(id: int, db: Session = Depends(get_db)):
    db_branch = db.query(models.Branch).filter(models.Branch.id == id).first()
    if not db_branch: raise HTTPException(404)
    db.delete(db_branch)
    db.commit()
    return {"status": "ok"}
