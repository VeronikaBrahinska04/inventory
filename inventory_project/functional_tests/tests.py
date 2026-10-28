import os
import shutil
import tempfile

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from playwright.sync_api import sync_playwright

from inventory_app.models import Product

os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

TEMP_MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class FunctionalTest(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.page = self.browser.new_page()

    def tearDown(self):
        self.page.close()


class AnonymousVisitorTest(FunctionalTest):
    def test_anonymous_visitor_cannot_add_a_product(self):
        # Mallory is not logged in. She opens the "Add Product" page directly
        self.page.goto(self.live_server_url + "/create/")

        # She should be sent to a login page instead of seeing the form
        # POSSIBLE BUG: product_create has no login check, the form is shown to anyone
        self.assertEqual(self.page.locator("input[name=name]").count(), 0)

        # Even so, she fills in the form and saves it
        if self.page.locator("input[name=name]").count():
            self.page.fill("input[name=name]", "Fake product")
            self.page.fill("input[name=price]", "1")
            self.page.fill("textarea[name=description]", "spam")
            self.page.fill("input[name=quantity]", "1")
            self.page.click("button[type=submit]")

        # No product should have been created
        self.assertEqual(Product.objects.count(), 0)

    def test_anonymous_visitor_cannot_delete_a_product(self):
        Product.objects.create(
            name="Laptop",
            price="999.99",
            image="products/laptop.png",
            description="A laptop",
            quantity=5,
        )

        # Mallory is not logged in. She opens the product list
        self.page.goto(self.live_server_url + "/products/")
        self.assertIn("Laptop", self.page.locator("body").inner_text())

        # She clicks "Delete" and confirms
        self.page.click("text=Delete")
        if self.page.locator("text=Yes Delete").count():
            self.page.click("text=Yes Delete")

        # The product should still be there
        # POSSIBLE BUG: product_delete has no login check, anyone can delete products
        self.assertEqual(Product.objects.count(), 1)


class AddProductWithoutImageTest(FunctionalTest):
    def test_product_list_still_works_after_adding_product_without_image(self):
        # Alice opens the product list and clicks "Add Product"
        self.page.goto(self.live_server_url + "/products/")
        self.page.click("text=Add Product")

        # She fills in everything but forgets to choose an image
        self.page.fill("input[name=name]", "Keyboard")
        self.page.fill("input[name=price]", "49.90")
        self.page.fill("textarea[name=description]", "Mechanical keyboard")
        self.page.fill("input[name=quantity]", "10")
        self.page.click("button[type=submit]")

        # She should either get an error message on the form, or see the list page.
        # The site should not show a server error.
        body = self.page.locator("body").inner_text()
        # POSSIBLE BUG: product saved without image, then product_list.html crashes on image.url
        self.assertNotIn("Server Error", body)
