from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.api import deps
from app.core.database import get_db
from app.core.models import StyleProfile, User
from app.schemas import ProfileCreate, ProfileResponse, ProfileUpdate
from app.agent.nodes.style_analyst import analyze_style
import uuid

router = APIRouter()

@router.get("/", response_model=List[ProfileResponse])
async def get_profiles(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
) -> Any:
    result = await db.execute(select(StyleProfile).where(StyleProfile.user_id == current_user.id))
    return result.scalars().all()

@router.post("/", response_model=ProfileResponse)
async def create_profile(
    profile_in: ProfileCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
) -> Any:
    profile = StyleProfile(
        name=profile_in.name,
        description=profile_in.description,
        tone_urls=profile_in.tone_urls,
        user_id=current_user.id
    )
    
    if profile_in.tone_urls:
        try:
            style_dna = await analyze_style(profile_in.tone_urls)
            profile.style_dna = style_dna
        except Exception as e:
            print(f"Style analysis failed: {e}")
            
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile

@router.get("/{profile_id}", response_model=ProfileResponse)
async def get_profile(
    profile_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
) -> Any:
    result = await db.execute(select(StyleProfile).where(StyleProfile.id == profile_id, StyleProfile.user_id == current_user.id))
    profile = result.scalars().first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile

@router.put("/{profile_id}", response_model=ProfileResponse)
async def update_profile(
    profile_id: uuid.UUID,
    profile_in: ProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
) -> Any:
    result = await db.execute(select(StyleProfile).where(StyleProfile.id == profile_id, StyleProfile.user_id == current_user.id))
    profile = result.scalars().first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
        
    if profile_in.name is not None:
        profile.name = profile_in.name
    if profile_in.description is not None:
        profile.description = profile_in.description
    
    # If tone_urls is updated, re-analyze
    if profile_in.tone_urls is not None:
        profile.tone_urls = profile_in.tone_urls
        try:
            style_dna = await analyze_style(profile_in.tone_urls)
            profile.style_dna = style_dna
        except Exception as e:
            print(f"Style analysis failed: {e}")
            
    if profile_in.style_dna is not None:
        profile.style_dna = profile_in.style_dna
        
    await db.commit()
    await db.refresh(profile)
    return profile

@router.delete("/{profile_id}", response_model=ProfileResponse)
async def delete_profile(
    profile_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
) -> Any:
    result = await db.execute(select(StyleProfile).where(StyleProfile.id == profile_id, StyleProfile.user_id == current_user.id))
    profile = result.scalars().first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
        
    await db.delete(profile)
    await db.commit()
    return profile