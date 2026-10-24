"""Operator-only reconciliation using provider-verified token counts.

python -m app.reconcile_usage CALL_UUID --input-tokens 100 --output-tokens 200
"""
import argparse
import asyncio
import uuid
from app.core.database import AsyncSessionLocal
from app.core.workspace_models import LLMCall
from app.services.metering import reconcile, MeterContext


async def main(args):
    async with AsyncSessionLocal() as db:
        call = await db.get(LLMCall, args.call_id)
        if not call:
            raise SystemExit('Call not found')
        if call.status != 'unresolved':
            raise SystemExit('Only unresolved calls can be reconciled; active and recorded calls are immutable')
        context = MeterContext(call.user_id, call.job_id)
    await reconcile(context, args.call_id, (args.input_tokens, args.output_tokens))
    print('Usage reconciled. The remaining reservation has been released.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('call_id', type=uuid.UUID)
    parser.add_argument('--input-tokens', type=int, required=True)
    parser.add_argument('--output-tokens', type=int, required=True)
    args = parser.parse_args()
    if min(args.input_tokens, args.output_tokens) < 0:
        parser.error('Token counts must be nonnegative')
    asyncio.run(main(args))
