from email.mime.base import MIMEBase
from unittest.mock import Mock, patch

from django.core.exceptions import ImproperlyConfigured
from django.core.mail import EmailMultiAlternatives
from django.test import SimpleTestCase, override_settings
from requests.exceptions import HTTPError

from base.backends import ConfiguredEmailBackend, ResendEmailBackend


@override_settings(
    EMAIL_PROVIDER="resend",
    RESEND_API_KEY="test-api-key",
    RESEND_FROM_EMAIL="Horilla <notifications@example.com>",
    RESEND_API_TIMEOUT=7,
)
class ResendEmailBackendTests(SimpleTestCase):
    @patch("base.backends.requests.post")
    def test_sends_html_and_text_alternatives_through_resend(self, post):
        response = Mock()
        post.return_value = response
        message = EmailMultiAlternatives(
            "Test subject",
            "Plain body",
            "ignored@example.com",
            ["employee@example.com"],
            cc=["manager@example.com"],
        )
        message.attach_alternative("<p>HTML body</p>", "text/html")
        message.attach(("report.txt", b"report", "text/plain"))
        inline_image = MIMEBase("image", "png")
        inline_image.set_payload(b"image-bytes")
        inline_image.add_header("Content-ID", "<company_logo>")
        message.attach(inline_image)

        sent = ResendEmailBackend().send_messages([message])

        self.assertEqual(sent, 1)
        post.assert_called_once_with(
            "https://api.resend.com/emails",
            headers={"Authorization": "Bearer test-api-key"},
            json={
                "from": "Horilla <notifications@example.com>",
                "to": ["employee@example.com"],
                "subject": "Test subject",
                "cc": ["manager@example.com"],
                "text": "Plain body",
                "html": "<p>HTML body</p>",
                "attachments": [
                    {"filename": "report.txt", "content": "cmVwb3J0"},
                    {
                        "filename": "attachment.png",
                        "content": "aW1hZ2UtYnl0ZXM=",
                        "content_id": "company_logo",
                    },
                ],
            },
            timeout=7,
        )
        response.raise_for_status.assert_called_once_with()

    @override_settings(RESEND_API_KEY="")
    def test_missing_api_key_is_reported(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "RESEND_API_KEY"):
            ResendEmailBackend().send_messages(
                [EmailMultiAlternatives("Subject", "Body", to=["to@example.com"])]
            )

    @patch("base.backends.requests.post")
    def test_resend_http_error_is_not_silenced(self, post):
        response = Mock()
        response.raise_for_status.side_effect = HTTPError("Resend rejected request")
        response.status_code = 422
        response.text = '{"message":"Invalid sender"}'
        post.return_value = response

        with self.assertRaisesMessage(RuntimeError, "Invalid sender"):
            ResendEmailBackend().send_messages(
                [EmailMultiAlternatives("Subject", "Body", to=["to@example.com"])]
            )

    @patch("base.backends.get_current_company", return_value=None)
    @patch("base.backends.EmailLog")
    @patch("base.backends.ResendEmailBackend")
    def test_configured_backend_routes_through_resend(
        self, resend_backend, email_log, _current_company
    ):
        resend_backend.return_value.send_messages.return_value = 1
        backend = Mock()
        backend.fail_silently = False
        backend.dynamic_from_email_with_display_name = "Horilla <hr@example.com>"
        message = EmailMultiAlternatives("Subject", "Body", to=["to@example.com"])

        sent = ConfiguredEmailBackend.send_messages(backend, [message])

        self.assertEqual(sent, 1)
        resend_backend.assert_called_once_with(fail_silently=False)
        resend_backend.return_value.send_messages.assert_called_once_with([message])
        email_log.assert_called_once()
        email_log.return_value.save.assert_called_once_with()
