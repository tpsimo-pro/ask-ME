from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.analysis.schemas import AnalyzeRequest, AnalyzeResponse
from app.analysis.service import run_analysis, AnalysisFailedError
from app.core.rate_limit import enforce_analyze_rate_limit
from app.db.models import Analysis, User
from app.db.session import get_db

router = APIRouter(tags=["analysis"])


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(
    request: AnalyzeRequest,
    current_user: User = Depends(enforce_analyze_rate_limit),
    db: Session = Depends(get_db),
):
    try:
        result = run_analysis(request.codigo, request.linguagem)
    except AnalysisFailedError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    analysis = Analysis(
        user_id=current_user.id,
        language=request.linguagem,
        code_snippet=request.codigo,
        suggestions=result.sugestoes,
        generated_tests=result.testes_gerados,
        security_risks=result.riscos_seguranca,
    )
    db.add(analysis)
    db.commit()

    return result
