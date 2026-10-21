import shutil
import tempfile
from unittest import mock

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template.loader import render_to_string
from django.test import Client, TestCase, override_settings

from inventory_app.models import Product


TEST_MEDIA_ROOT = tempfile.mkdtemp()

# Smallest valid GIF image, used for uploads.
SMALL_GIF = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff"
    b"!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01"
    b"\x00\x00\x02\x02D\x01\x00;"
)


def make_image(name="test.gif"):
    return SimpleUploadedFile(name, SMALL_GIF, content_type="image/gif")


def valid_product_data(**overrides):
    data = {
        "name": "Laptop",
        "price": "999.99",
        "description": "A fast laptop",
        "quantity": "5",
    }
    data.update(overrides)
    return data


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class BaseTest(TestCase):
    """Server errors come back as a 500 response instead of an exception,
    so a bug makes the test FAIL (not ERROR)."""

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.client = Client(raise_request_exception=False)

    def create_product(self, **overrides):
        fields = {
            "name": "Phone",
            "price": "199.99",
            "image": make_image(),
            "description": "A smart phone",
            "quantity": 3,
        }
        fields.update(overrides)
        return Product.objects.create(**fields)


# ---------------------------------------------------------------------------
# Bug 1: send_test_email renders a template that does not exist
# ---------------------------------------------------------------------------
class SendTestEmailTest(BaseTest):
    # POSSIBLE BUG: views.py asks for 'Email_Seent.html', the file is 'email_sent.html'
    def test_email_page_renders_without_server_error(self):
        response = self.client.get("/send-test-email/")
        self.assertEqual(response.status_code, 200)

    # POSSIBLE BUG: views.py asks for 'Email_Seent.html', the file is 'email_sent.html'
    def test_email_page_uses_email_sent_template(self):
        response = self.client.get("/send-test-email/")
        self.assertTemplateUsed(response, "email_sent.html")

    # POSSIBLE BUG: the error branch uses the same missing template
    def test_email_error_page_renders_without_server_error(self):
        with mock.patch(
            "inventory_app.views.send_mail", side_effect=Exception("SMTP is down")
        ):
            response = self.client.get("/send-test-email/")
        self.assertEqual(response.status_code, 200)


# ---------------------------------------------------------------------------
# Bug 2: email page ignores the message and always says "success"
# ---------------------------------------------------------------------------
class EmailSentTemplateTest(TestCase):
    # POSSIBLE BUG: email_sent.html never prints {{ message }}
    def test_template_shows_message_from_view(self):
        html = render_to_string(
            "email_sent.html", {"message": "Error sending email: SMTP is down"}
        )
        self.assertIn("Error sending email: SMTP is down", html)

    # POSSIBLE BUG: success text is hard-coded in email_sent.html
    def test_template_does_not_claim_success_when_sending_failed(self):
        html = render_to_string(
            "email_sent.html", {"message": "Error sending email: SMTP is down"}
        )
        self.assertNotIn("Email Sent Successfully!", html)


# ---------------------------------------------------------------------------
# Bug 3: "Back to Home" link points to "/" which does not exist
# ---------------------------------------------------------------------------
class HomePageTest(BaseTest):
    # POSSIBLE BUG: no URL pattern for "/", but email_sent.html links to it
    def test_home_page_link_target_exists(self):
        response = self.client.get("/")
        self.assertNotEqual(response.status_code, 404)


# ---------------------------------------------------------------------------
# Bug 4: a product without an image breaks the list / detail / update pages
# ---------------------------------------------------------------------------
class ProductWithoutImageTest(BaseTest):
    # POSSIBLE BUG: view saves product without image, then product.image.url crashes
    def test_list_page_works_after_adding_product_without_image(self):
        self.client.post("/create/", data=valid_product_data())
        response = self.client.get("/products/")
        self.assertEqual(response.status_code, 200)

    # POSSIBLE BUG: product_detail.html calls product.image.url with no file
    def test_detail_page_works_for_product_without_image(self):
        product = self.create_product(image="")
        response = self.client.get(f"/product/{product.id}/")
        self.assertEqual(response.status_code, 200)

    # POSSIBLE BUG: product_update.html calls product.image.url with no file
    def test_update_page_works_for_product_without_image(self):
        product = self.create_product(image="")
        response = self.client.get(f"/update/{product.id}/")
        self.assertEqual(response.status_code, 200)


# ---------------------------------------------------------------------------
# Bugs 5-8: create view has no input validation
# ---------------------------------------------------------------------------
class ProductCreateValidationTest(BaseTest):
    def post_create(self, **overrides):
        data = valid_product_data(**overrides)
        data["image"] = make_image()
        return self.client.post("/create/", data=data)

    # Bug 5
    # POSSIBLE BUG: empty price goes straight to the database -> 500
    def test_empty_price_does_not_crash(self):
        response = self.post_create(price="")
        self.assertNotEqual(response.status_code, 500)
        self.assertEqual(Product.objects.count(), 0)

    # POSSIBLE BUG: non-numeric price goes straight to the database -> 500
    def test_text_price_does_not_crash(self):
        response = self.post_create(price="abc")
        self.assertNotEqual(response.status_code, 500)
        self.assertEqual(Product.objects.count(), 0)

    # POSSIBLE BUG: price bigger than max_digits=10 is not checked
    def test_too_large_price_is_not_saved(self):
        response = self.post_create(price="123456789012.99")
        self.assertNotEqual(response.status_code, 500)
        self.assertEqual(Product.objects.count(), 0)

    # Bug 10
    # POSSIBLE BUG: too large price is saved, then reading it back crashes the list
    def test_list_page_works_after_posting_too_large_price(self):
        self.post_create(price="123456789012.99")
        response = self.client.get("/products/")
        self.assertEqual(response.status_code, 200)

    # Bug 6
    # POSSIBLE BUG: empty quantity goes straight to the database -> 500
    def test_empty_quantity_does_not_crash(self):
        response = self.post_create(quantity="")
        self.assertNotEqual(response.status_code, 500)
        self.assertEqual(Product.objects.count(), 0)

    # POSSIBLE BUG: non-numeric quantity goes straight to the database -> 500
    def test_text_quantity_does_not_crash(self):
        response = self.post_create(quantity="abc")
        self.assertNotEqual(response.status_code, 500)
        self.assertEqual(Product.objects.count(), 0)

    # Bug 7
    # POSSIBLE BUG: negative quantity breaks the PositiveIntegerField check -> 500
    def test_negative_quantity_does_not_crash(self):
        response = self.post_create(quantity="-5")
        self.assertNotEqual(response.status_code, 500)
        self.assertEqual(Product.objects.count(), 0)

    # Bug 8
    # POSSIBLE BUG: empty name is saved without any check
    def test_empty_name_is_not_saved(self):
        self.post_create(name="")
        self.assertEqual(Product.objects.count(), 0)

    # POSSIBLE BUG: missing name field becomes None -> NOT NULL error -> 500
    def test_missing_name_field_does_not_crash(self):
        data = valid_product_data()
        del data["name"]
        data["image"] = make_image()
        response = self.client.post("/create/", data=data)
        self.assertNotEqual(response.status_code, 500)
        self.assertEqual(Product.objects.count(), 0)


# ---------------------------------------------------------------------------
# Bug 9: update view has the same missing validation
# ---------------------------------------------------------------------------
class ProductUpdateValidationTest(BaseTest):
    def setUp(self):
        super().setUp()
        self.product = self.create_product()

    def post_update(self, **overrides):
        data = valid_product_data(**overrides)
        return self.client.post(f"/update/{self.product.id}/", data=data)

    # POSSIBLE BUG: empty price on update -> 500
    def test_empty_price_does_not_crash(self):
        response = self.post_update(price="")
        self.assertNotEqual(response.status_code, 500)

    # POSSIBLE BUG: empty quantity on update -> 500
    def test_empty_quantity_does_not_crash(self):
        response = self.post_update(quantity="")
        self.assertNotEqual(response.status_code, 500)

    # POSSIBLE BUG: negative quantity on update -> 500
    def test_negative_quantity_does_not_crash(self):
        response = self.post_update(quantity="-1")
        self.assertNotEqual(response.status_code, 500)

    # POSSIBLE BUG: empty name overwrites the real name
    def test_empty_name_does_not_overwrite_product_name(self):
        self.post_update(name="")
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, "Phone")


# ---------------------------------------------------------------------------
# Sanity checks: normal behaviour that should work (expected to PASS)
# ---------------------------------------------------------------------------
class ProductHappyPathTest(BaseTest):
    def test_can_create_product_with_valid_data(self):
        data = valid_product_data()
        data["image"] = make_image()
        response = self.client.post("/create/", data=data)
        self.assertRedirects(response, "/products/")
        self.assertEqual(Product.objects.get().name, "Laptop")

    def test_list_page_shows_products(self):
        self.create_product(name="Phone")
        response = self.client.get("/products/")
        self.assertContains(response, "Phone")

    def test_delete_removes_product(self):
        product = self.create_product()
        self.client.post(f"/delete/{product.id}/")
        self.assertEqual(Product.objects.count(), 0)

    def test_send_test_email_sends_one_email(self):
        self.client.get("/send-test-email/")
        self.assertEqual(len(mail.outbox), 1)
