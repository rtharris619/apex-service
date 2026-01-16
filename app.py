from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Literal, Optional, Dict, Any
import fastf1
import pandas as pd


fastf1.Cache.enable_cache("./fastf1_cache")


app = FastAPI(title="Apex Compute Service", version="1.0.0")


class SessionRequest(BaseModel):
  year: int = Field(..., ge=1950, le=2100)
  gp: str = Field(..., description="Grand Prix name or round number as string, e.g. 'Bahrain' or '1'")
  session: Literal["FP1", "FP2", "FP3", "Q", "SQ", "R"]


@app.get("/health")
def health():
  return {"status": "ok"}


@app.post("/session/info")
def session_info(req: SessionRequest) -> Dict[str, Any]:
  """
  Returns basic session metadata + drivers list.
  """
  try:
    session = fastf1.get_session(req.year, req.gp, req.session)
    session.load()
  except Exception as e:
    raise HTTPException(status_code=400, detail=f"FastF1 error: {e}")
  
  drivers = []
  try:
    drivers = list(session.drivers)
  except Exception:
    drivers = []

  return {
    "year": req.year,
    "gp": req.gp,
    "session": req.session,
    "session_name": getattr(session, "name", None),
    "drivers": drivers
  }


@app.post("/session/laps")
def session_laps(req: SessionRequest, driver: Optional[str] = None) -> Dict[str, Any]:
  """
  Returns lap table (optionally filtered by driver) in JSON.
  Note: returning *all* laps can be large; consider paging/filters.
  """
  try:
    session = fastf1.get_session(req.year, req.gp, req.session)
    session.load(laps=True, telemetry=False, weather=False, messages=False)
    laps = session.laps

    if driver:
      laps = laps.pick_driver(driver)

    cols = [c for c in [
      "Driver", "LapNumber", "Stint", "Compound", "TyreLife",
      "LapTime", "Sector1Time", "Sector2Time", "Sector3Time",
      "SpeedI1", "SpeedI2", "SpeedFL", "SpeedST",
      "IsPersonalBest", "Deleted", "TrackStatus"
    ] if c in laps.columns]

    df = laps[cols].copy()

    for c in df.columns:
      if pd.api.types.is_timedelta64_dtype(df[c]):
        df[c] = df[c].dt.total_seconds().mul(1000).round().astype("Int64")

    records = df.where(pd.notnull(df), None).to_dict(orient="records")

    return { "count": len(records), "data": records }

  except Exception as e:
    raise HTTPException(status_code=400, detail=f"FastF1 error: {e}")
  

