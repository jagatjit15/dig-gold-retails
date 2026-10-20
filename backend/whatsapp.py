"""WhatsApp provider slot.

To plug in your provider: subclass WhatsAppProvider, implement send_text and
send_document (read your own credentials from env), add it to PROVIDERS, and set
WHATSAPP_PROVIDER in backend/.env to its key. The default "mock" provider only
records messages in the outbox; nothing is actually sent.
"""
import logging
import os
import re
from typing import Optional

from db import db
from invoice_pdf import build_invoice_pdf
from models import new_id, now_iso

logger = logging.getLogger("swarnaerp.whatsapp")


class WhatsAppProvider:
    name = "base"
    mocked = False

    async def send_text(self, to: str, text: str) -> dict:
        raise NotImplementedError

    async def send_document(self, to: str, filename: str, data: bytes, mime: str,
                            caption: str) -> dict:
        raise NotImplementedError

    async def send_image(self, to: str, filename: str, data: bytes, caption: str) -> dict:
        return await self.send_document(to, filename, data, "image/png", caption)


class MockProvider(WhatsAppProvider):
    name = "mock"
    mocked = True

    async def send_text(self, to, text):
        logger.info("[MOCK WhatsApp] text to %s: %s", to, text[:80])
        return {"status": "mocked", "provider_message_id": None}

    async def send_document(self, to, filename, data, mime, caption):
        logger.info("[MOCK WhatsApp] document %s (%d bytes) to %s", filename, len(data), to)
        return {"status": "mocked", "provider_message_id": None}


PROVIDERS = {"mock": MockProvider}


def get_provider() -> WhatsAppProvider:
    return PROVIDERS[os.environ["WHATSAPP_PROVIDER"]]()


def normalize_phone(raw: Optional[str]) -> Optional[str]:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 10:
        digits = "91" + digits
    return digits if 11 <= len(digits) <= 15 else None


async def record_message(**fields) -> dict:
    rec = {"id": new_id(), "created_at": now_iso(), **fields}
    await db.whatsapp_messages.insert_one(rec)
    rec.pop("_id", None)
    return rec


async def send_invoice_message(bill: dict, branch: dict, actor_id: str) -> dict:
    provider = get_provider()
    to = normalize_phone(bill.get("customer_phone"))
    base = {"kind": "invoice", "bill_id": bill["id"], "branch_id": bill["branch_id"],
            "to": to or bill.get("customer_phone"), "provider": provider.name,
            "created_by": actor_id}
    if not to:
        return await record_message(**base, status="invalid_number", error="Invalid phone number")
    payable = bill.get("net_payable")
    payable = bill["grand_total"] if payable is None else payable
    caption = (f"Dear {bill['customer_name']}, thank you for shopping at {branch['name']}. "
               f"Your invoice {bill['bill_no']} for Rs. {payable:,.2f} is attached.")
    try:
        pdf = build_invoice_pdf(bill, branch)
        res = await provider.send_document(to, f"{bill['bill_no']}.pdf", pdf,
                                           "application/pdf", caption)
        return await record_message(**base, status=res.get("status", "sent"),
                                    provider_message_id=res.get("provider_message_id"),
                                    text=caption)
    except Exception as e:
        logger.exception("WhatsApp invoice send failed")
        return await record_message(**base, status="failed", error=str(e), text=caption)
