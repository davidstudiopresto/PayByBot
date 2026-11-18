"""One rule for « already signed up », at sign-in and at the sign-up page's check: an e-mail, a subscription or a
renewal. A row saved without any of them (an admin's background reads) is not one, else sign-in says « no account »
while the sign-up says « already exists » and nobody can get in."""
import json
import os
import unittest
from unittest.mock import MagicMock, patch

from paybybot3 import web


class SignupCheck(unittest.TestCase):
    def check(self, account, renewals=None):
        os.environ["PAYBYBOT_SECRET"] = "t"
        sealed = web._fernet("account").encrypt(json.dumps(account).encode()).decode() if account is not None else None

        def store(fn, **kw):
            if fn == "rate_hit":
                return True
            if fn == "account_get":
                return sealed
            if fn == "renewal_list":
                return renewals

        request = MagicMock(headers={"x-real-ip": "1.2.3.4"})
        with patch.object(web, "HOSTED", True), patch.object(web, "store", side_effect=store):
            return web.signup_check(web.SignupCheck(username="+33777920788"), request)["exists"]

    def test_an_account_without_email_is_not_signed_up(self):
        self.assertFalse(self.check({"zone": "75005"}))

    def test_an_account_with_email_or_renewals_is(self):
        self.assertTrue(self.check({"email": "a@b.fr"}))
        self.assertTrue(self.check({"stripe_subscription": "sub_1"}))
        self.assertTrue(self.check({}, renewals="x"))

    def test_no_account(self):
        self.assertFalse(self.check(None))


if __name__ == "__main__":
    unittest.main()


class SignupZone(unittest.TestCase):
    def test_found_while_the_code_is_read_and_kept_for_it(self):
        pending = {"email": "a@b.fr", "zone": None, "t": "tok"}
        response = MagicMock()
        with patch.object(web, "HOSTED", False), patch.object(web, "read_pending", return_value=(pending, MagicMock())), \
                patch.object(web, "resident_home_zone", return_value="75005"):
            self.assertEqual(web.signup_zone(response, "tok"), {"zone": "75005"})
        self.assertEqual(pending["zone"], "75005")

    def test_a_failed_search_never_blocks(self):
        pending = {"email": "a@b.fr", "zone": None, "t": "tok"}
        with patch.object(web, "HOSTED", False), patch.object(web, "read_pending", return_value=(pending, MagicMock())), \
                patch.object(web, "resident_home_zone", side_effect=RuntimeError("429")):
            self.assertEqual(web.signup_zone(MagicMock(), "tok"), {"zone": None})
