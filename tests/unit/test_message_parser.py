from datetime import datetime, timezone
import pytz
import pytest

from app.services.message_parser import (
    extract_sequence_number,
    extract_sender_phone,
    extract_timestamp,
    get_shift,
    has_image,
)


class TestExtractSequenceNumber:
    def test_simple_format(self):
        assert extract_sequence_number("47/200") == 47

    def test_with_surrounding_text(self):
        assert extract_sequence_number("Treino feito! 100/200 hoje") == 100

    def test_first_workout(self):
        assert extract_sequence_number("1/200") == 1

    def test_goal_reached(self):
        assert extract_sequence_number("200/200") == 200

    def test_no_match(self):
        assert extract_sequence_number("oi pessoal") is None

    def test_zero_rejected(self):
        assert extract_sequence_number("0/200") is None

    def test_over_200_rejected(self):
        assert extract_sequence_number("201/200") is None

    def test_case_insensitive(self):
        assert extract_sequence_number("50/200") == 50


class TestGetShift:
    tz = "America/Sao_Paulo"

    def _dt(self, hour: int, minute: int = 0) -> datetime:
        brt = pytz.timezone(self.tz)
        return brt.localize(datetime(2026, 3, 15, hour, minute))

    def test_madrugada(self):
        assert get_shift(self._dt(3), self.tz) == "madrugada"

    def test_manha(self):
        assert get_shift(self._dt(9), self.tz) == "manha"

    def test_tarde(self):
        assert get_shift(self._dt(15), self.tz) == "tarde"

    def test_noite(self):
        assert get_shift(self._dt(20), self.tz) == "noite"

    def test_shift_boundary_manha_start(self):
        assert get_shift(self._dt(6, 0), self.tz) == "manha"

    def test_shift_boundary_tarde_start(self):
        assert get_shift(self._dt(12, 0), self.tz) == "tarde"

    def test_shift_boundary_noite_start(self):
        assert get_shift(self._dt(18, 0), self.tz) == "noite"


class TestExtractSenderPhone:
    def _group_payload(self, phone: str) -> dict:
        return {
            "data": {
                "key": {
                    "remoteJid": "5511GROUP@g.us",
                    "fromMe": False,
                    "id": "MSGID",
                    "participant": f"{phone}@s.whatsapp.net",
                }
            }
        }

    def _dm_payload(self, phone: str) -> dict:
        return {
            "data": {
                "key": {
                    "remoteJid": f"{phone}@s.whatsapp.net",
                    "fromMe": False,
                    "id": "MSGID",
                }
            }
        }

    def test_group_message_extracts_participant(self):
        assert extract_sender_phone(self._group_payload("5511999990000")) == "5511999990000"

    def test_dm_extracts_remote_jid(self):
        assert extract_sender_phone(self._dm_payload("5511888880000")) == "5511888880000"

    def test_missing_key_returns_none(self):
        assert extract_sender_phone({}) is None


class TestHasImage:
    def test_detects_image(self):
        assert has_image({"imageMessage": {"mimetype": "image/jpeg"}}) is True

    def test_no_image(self):
        assert has_image({"conversation": "hello"}) is False
