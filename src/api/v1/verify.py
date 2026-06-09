from fastapi import APIRouter

from src.schemas.verify import StatelessVerifyRequest, StatelessVerifyResponse
from src.services.merkle import compute_raw_event_hash, verify_proof

router = APIRouter(tags=["verify"])


@router.post("/verify", response_model=StatelessVerifyResponse)
async def stateless_verify(
    data: StatelessVerifyRequest,
):
    _, event_hash = compute_raw_event_hash(data.session_id, data.sequence_no, data.payload)
    proof_path = [step.model_dump() for step in data.proof_path]
    valid = verify_proof(event_hash, proof_path, data.hex_root)
    return {"valid": valid}
