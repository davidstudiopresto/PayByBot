"""PayByPhone's paid SMS: read from the member's consents, turned off or on only by the user's own tap, and never shown
when PayByPhone does not say (no guessed state)."""
import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from paybybot3 import web
from paybybot3.bot import Bot as PayByPhone


def consent(name, kind):
    return {"purposeName": name, "purposeVersion": "v1", "purposeLanguage": "fr-FR", "consentType": kind}


class Bot(unittest.TestCase):
    def bot(self, *answers):
        b = PayByPhone.__new__(PayByPhone)
        b._graphql = MagicMock(side_effect=list(answers))
        return b

    def test_only_the_paid_sms_are_read(self):
        b = self.bot({"getMemberConsentsV1": [consent("TermsAndConditions", "OptIn"), consent("SmsReceipts", "OptOut"),
                                              consent("SmsReminders", "OptIn")]})
        self.assertEqual(sorted(b.get_sms_consents()), ["SmsReceipts", "SmsReminders"])

    def test_turning_off_sends_both_opt_outs_with_input(self):
        b = self.bot({"getMemberConsentsV1": [consent("SmsReceipts", "OptIn")]},
                     {"createMemberConsentsV1": {"generalResponse": {"success": True}}})
        b.set_sms_consents(False)
        query, variables = b._graphql.call_args.args
        self.assertIn("(input: $input)", query)
        self.assertEqual({c["purposeName"]: c["consentType"] for c in variables["input"]["request"]["consents"]},
                         {"SmsReceipts": "OptOut", "SmsReminders": "OptOut"})

    def test_a_refusal_is_an_error(self):
        b = self.bot({"getMemberConsentsV1": []}, {"createMemberConsentsV1": {"generalResponse": {"success": False}}})
        with self.assertRaises(RuntimeError):
            b.set_sms_consents(False)


class Routes(unittest.TestCase):
    def session(self, consents):
        s = MagicMock(demo=False)
        s.call.side_effect = lambda method, *a: consents() if method == "get_sms_consents" else None
        return s

    def test_on_when_one_is_opted_in(self):
        s = self.session(lambda: {"SmsReceipts": consent("SmsReceipts", "OptIn")})
        self.assertTrue(web.sms_enabled(s))

    def test_unknown_when_unreadable(self):
        def fail():
            raise RuntimeError("down")
        self.assertIsNone(web.sms_enabled(self.session(fail)))
        self.assertIsNone(web.sms_enabled(self.session(lambda: {})))

    def test_a_change_not_kept_by_paybyphone_is_a_502(self):
        s = self.session(lambda: {"SmsReceipts": consent("SmsReceipts", "OptIn")})  # still on after « off »
        with patch.object(web, "current", return_value=s), self.assertRaises(HTTPException) as e:
            web.sms_set(web.SmsSetting(enabled=False), "t")
        self.assertEqual(e.exception.status_code, 502)


if __name__ == "__main__":
    unittest.main()
