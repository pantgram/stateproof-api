from fastapi import APIRouter

from src.schemas.verify import StatelessVerifyRequest, StatelessVerifyResponse
from src.services.merkle import verify_proof

router = APIRouter(tags=["verify"])


# This endpoint works for both tree levels:
#
# For event-level verify:
#   leaf_hash = client computed event hash
#   proof_path = from GET .../events/{seq}/proof
#   hex_root = session.session_hash
#
# For session-level verify:
#   leaf_hash = session.leaf_hash
#   proof_path = from GET .../sessions/{id}/proof
#   hex_root = workflow.hex_root
@router.post("/verify", response_model=StatelessVerifyResponse)
async def stateless_verify(
    data: StatelessVerifyRequest,
):
    proof_path = [step.model_dump() for step in data.proof_path]
    valid = verify_proof(data.leaf_hash, proof_path, data.hex_root)
    return {"valid": valid}
