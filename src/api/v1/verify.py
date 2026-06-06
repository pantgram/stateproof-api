from fastapi import APIRouter

from src.schemas.verify import StatelessVerifyRequest, StatelessVerifyResponse
from src.services.merkle import verify_proof

router = APIRouter(tags=["verify"])


@router.post("/verify", response_model=StatelessVerifyResponse)
async def stateless_verify(
    data: StatelessVerifyRequest,
):
    proof_path = [step.model_dump() for step in data.proof_path]
    valid = verify_proof(data.leaf_hash, proof_path, data.hex_root)
    return {"valid": valid}
