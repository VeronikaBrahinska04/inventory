# Bug report: Inventory project

**Date:** 2026-10-28
**Scope:** `inventory_project/inventory_app` (views, URLs, models, templates) and `inventory_project/settings.py`
**Application code changed:** none. Only test files and this report were added.

## How to run the tests

From `inventory/inventory_project`:

```
python manage.py test inventory_app      # unit tests (31)
python manage.py test functional_tests   # Playwright browser tests (3)
python manage.py test                    # everything (34)
```

**Result:** 34 tests ran. **28 failed**, and every one of those failures is caused by a bug. 6 passed (see "Checked: works correctly").
Each failing test has a `# POSSIBLE BUG:` comment above the line that fails.

| Group | Bugs | Confirmed | Not confirmed |
|---|---|---|---|
| A. Security and access control | 6 | 6 | 0 |
| B. Crashes and missing input checks | 10 | 10 | 0 |
| **Total** | **16** | **16** | **0** |

> **Urgent, outside the code:** `settings.py` contains a real Gmail address and app password (Bug 6). It is in the git history, so deleting it from the file is not enough. The password should be **revoked in the Google account** now.

---

## A. Security and access control

### Who can create, edit and delete products?

| Action | Expected | Actual |
|---|---|---|
| Create a product | Only logged-in users with the `add_product` permission | **Anyone, even without logging in** |
| Edit a product | Only logged-in users with the `change_product` permission | **Anyone, even without logging in** |
| Delete a product | Only logged-in users with the `delete_product` permission | **Anyone, even without logging in** |
| Send the test email | Admin only, or not reachable at all | **Anyone, even without logging in** |

There is no login page in the project either. No URL is defined for `accounts/login/`, so users have no way to sign in on the site.

---

### Bug 1: Anyone can create products without logging in

**In simple words:** A stranger on the internet can open `/create/` and add as many products as they like. Nobody asks them who they are.

**Cause:** [inventory_app/views.py:19](inventory_project/inventory_app/views.py#L19). `def product_create(request):` has no `@login_required` decorator and no other login check. The URL is public at [inventory_app/urls.py:7](inventory_project/inventory_app/urls.py#L7).

**Tests (fail):**
- `inventory_app.tests.ProductCreateAccessTest.test_anonymous_user_cannot_open_create_page`: page returns `200` (expected a redirect to login)
- `inventory_app.tests.ProductCreateAccessTest.test_anonymous_user_cannot_create_product`: `1 != 0` (a product was created)
- `functional_tests.tests.AnonymousVisitorTest.test_anonymous_visitor_cannot_add_a_product` (browser): the form is shown and the product is saved

---

### Bug 2: Anyone can edit any product without logging in

**In simple words:** A stranger can change the name, price or quantity of any product. For example, they could set every price to 1.

**Cause:** [inventory_app/views.py:41](inventory_project/inventory_app/views.py#L41). `def product_update(request, pk):` has no login check. Lines 45–53 save whatever was sent.

**Tests (fail):**
- `ProductUpdateAccessTest.test_anonymous_user_cannot_open_update_page`: `200`
- `ProductUpdateAccessTest.test_anonymous_user_cannot_update_product`: `'Hacked' != 'Phone'` (the name was changed)

---

### Bug 3: Anyone can delete any product without logging in

**In simple words:** A stranger can wipe out the whole inventory by clicking "Delete" → "Yes Delete" for each product. A simple script could do it in seconds.

**Cause:** [inventory_app/views.py:61](inventory_project/inventory_app/views.py#L61). `def product_delete(request, pk):` has no login check. Line 65 `product.delete()` runs for any POST request.

**Tests (fail):**
- `ProductDeleteAccessTest.test_anonymous_user_cannot_open_delete_page`: `200`
- `ProductDeleteAccessTest.test_anonymous_user_cannot_delete_product`: the product is gone
- `functional_tests.tests.AnonymousVisitorTest.test_anonymous_visitor_cannot_delete_a_product` (browser): `0 != 1`

---

### Bug 4: Logged-in users without permission can still create, edit and delete

**In simple words:** Django has a permission system ("this user may add products, that user may only look"), but the app never uses it. Any account, even one with no permissions at all, can do everything.

**Cause:** [inventory_app/views.py:19](inventory_project/inventory_app/views.py#L19), [views.py:41](inventory_project/inventory_app/views.py#L41) and [views.py:61](inventory_project/inventory_app/views.py#L61). There is no `@permission_required('inventory_app.add_product')` (or `change_product` / `delete_product`) and no `request.user.has_perm(...)` check.

**Tests (fail):**
- `ProductCreateAccessTest.test_user_without_add_permission_cannot_create_product`: `1 != 0`
- `ProductUpdateAccessTest.test_user_without_change_permission_cannot_update_product`: `'Hacked' != 'Phone'`
- `ProductDeleteAccessTest.test_user_without_delete_permission_cannot_delete_product`: the product is gone

---

### Bug 5: Anyone can make the server send emails

**In simple words:** Every visit to `/send-test-email/` sends a real email from the project's Gmail account. Anyone who finds the address can make it send emails over and over. That can get the Gmail account blocked for spam.

**Cause:** [inventory_app/views.py:69](inventory_project/inventory_app/views.py#L69). `send_test_email` has no login or admin check, and it is a public URL at [inventory_app/urls.py:10](inventory_project/inventory_app/urls.py#L10). The email is sent on a simple GET request (line 76).

**Test (fails):** `SendTestEmailAccessTest.test_anonymous_user_cannot_trigger_email`: `1 != 0` (an email was sent). The test uses Django's in-memory email backend, so no real email went out.

---

### Bug 6: Secret key and Gmail password are written in the settings file

**In simple words:** The "master key" of the site and the password of a Gmail account are stored as plain text in the code. Anyone who can see the code (for example on GitHub) can read them. With the Gmail password they can send emails as that account. With the secret key they can forge login sessions and other signed data.

**Cause:**
- [inventory_project/settings.py:23](inventory_project/inventory_project/settings.py#L23): `SECRET_KEY = 'django-insecure-...'`, the hard-coded development key
- [inventory_project/settings.py:129-130](inventory_project/inventory_project/settings.py#L129-L130): `EMAIL_HOST_USER` and `EMAIL_HOST_PASSWORD` are hard-coded
- Related: [settings.py:26](inventory_project/inventory_project/settings.py#L26) `DEBUG = True`. If this were deployed, error pages would show code and settings to visitors. The test runner always forces `DEBUG = False`, so this one is noted here but has no test.

**Tests (fail):**
- `SecretsInSettingsTest.test_secret_key_is_not_the_insecure_default`
- `SecretsInSettingsTest.test_email_password_is_not_hardcoded_in_settings`: finds `EMAIL_HOST_PASSWORD = '` written as a plain string in `settings.py`

---

## B. Crashes and missing input checks

The app reads form values directly with `request.POST.get(...)` and saves them without any checks. There is no Django `Form` or `ModelForm`. Bugs 9–15 come from this.

### Bug 7: The "send test email" page always crashes

**In simple words:** The page for sending a test email always shows "Server Error (500)". The email is actually sent first, so the user gets an error even though it worked.

**Cause:** [inventory_app/views.py:77](inventory_project/inventory_app/views.py#L77) and [views.py:79](inventory_project/inventory_app/views.py#L79) render `'Email_Seent.html'`. That file does not exist. The real file is `templates/email_sent.html` (different spelling: "Seent"). The `except` block on line 79 uses the same wrong name, so it crashes again.
Error: `TemplateDoesNotExist: Email_Seent.html`

**Test (fails):** `SendTestEmailTest.test_send_test_email_page_renders`: `500 != 200`

---

### Bug 8: The email page always says "success", even when sending failed

**In simple words:** Even if Bug 7 is fixed, the page will always say "Email Sent Successfully!", even when the email could not be sent. The user is never told about the error.

**Cause:** [inventory_app/templates/email_sent.html:93-94](inventory_project/inventory_app/templates/email_sent.html#L93-L94) contain fixed "success" text. The view passes a `message` (success or `Error sending email: ...`, [views.py:77-79](inventory_project/inventory_app/views.py#L77-L79)), but the template never shows `{{ message }}`.

**Test (fails):** `SendTestEmailTest.test_email_sent_page_shows_the_message`: the error text is missing and "Email Sent Successfully!" is shown

---

### Bug 9: A product without an image breaks the product list, detail and edit pages

**In simple words:** If someone adds a product and forgets to choose a picture, the product is still saved. After that, **the whole product list shows "Server Error (500)"** for everyone, so nobody can see any product until that one is removed through the admin. Its detail page and edit page crash too.

**Cause:**
1. [inventory_app/views.py:23](inventory_project/inventory_app/views.py#L23) and [views.py:27-33](inventory_project/inventory_app/views.py#L27-L33). The view saves the product even when no image was uploaded. The model says the image is required ([models.py:7](inventory_project/inventory_app/models.py#L7)), but `objects.create()` does not check that.
2. The templates then call `product.image.url` on an empty image, which raises `ValueError: The 'image' attribute has no file associated with it.`:
   - [templates/product_list.html:19](inventory_project/inventory_app/templates/product_list.html#L19)
   - [templates/product_detail.html:12](inventory_project/inventory_app/templates/product_detail.html#L12)
   - [templates/product_update.html:24](inventory_project/inventory_app/templates/product_update.html#L24)

**Tests (fail):**
- `ProductWithoutImageTest.test_cannot_create_product_without_image`: `1 != 0`
- `ProductWithoutImageTest.test_product_list_still_works_after_product_without_image`: `500 != 200`
- `ProductWithoutImageTest.test_detail_page_works_for_product_without_image`: `500 != 200`
- `ProductWithoutImageTest.test_update_page_works_for_product_without_image`: `500 != 200`
- `functional_tests.tests.AddProductWithoutImageTest.test_product_list_still_works_after_adding_product_without_image` (browser): the page shows `Server Error (500)` right after clicking "Save Product"

---

### Bug 10: Submitting an empty "Add Product" form crashes the server

**In simple words:** Clicking "Save Product" with empty fields shows "Server Error (500)" instead of a message like "Please enter a name".

**Cause:** [inventory_app/views.py:21-33](inventory_project/inventory_app/views.py#L21-L33). Missing fields become `None` and are passed straight to `Product.objects.create(...)`. The database refuses empty values.
Error: `IntegrityError: NOT NULL constraint failed: inventory_app_product.name`

**Test (fails):** `ProductCreateValidationTest.test_empty_form_does_not_crash`: `500`

---

### Bug 11: A negative quantity crashes the server

**In simple words:** Typing `-1` as the quantity shows "Server Error (500)" instead of "Quantity cannot be negative".

**Cause:** [inventory_app/views.py:25](inventory_project/inventory_app/views.py#L25) reads the quantity with no check. The model field is `PositiveIntegerField` ([models.py:9](inventory_project/inventory_app/models.py#L9)), so the database rejects `-1`. The app does not catch this.
Error: `IntegrityError: CHECK constraint failed: quantity`

**Test (fails):** `ProductCreateValidationTest.test_negative_quantity_does_not_crash`: `500`

---

### Bug 12: Text in the price field crashes the server

**In simple words:** If the price is `abc` instead of a number, the site crashes. The browser's number field normally stops this, but anyone can send the request without the browser.

**Cause:** [inventory_app/views.py:22](inventory_project/inventory_app/views.py#L22) passes the raw text to `DecimalField`.
Error: `ValidationError: "abc" value must be a decimal number.`

**Test (fails):** `ProductCreateValidationTest.test_text_price_does_not_crash`: `500`

---

### Bug 13: A negative price is accepted

**In simple words:** A product can be saved with a price of `-50.00`. That makes no sense for an inventory and would break any totals.

**Cause:** [inventory_app/views.py:22](inventory_project/inventory_app/views.py#L22) has no check. [models.py:6](inventory_project/inventory_app/models.py#L6) `DecimalField` has no `MinValueValidator(0)`, and validators would not run anyway, because the view uses `objects.create()` and not a form.

**Test (fails):** `ProductCreateValidationTest.test_negative_price_is_rejected`: `1 != 0` (saved)

---

### Bug 14: A product with an empty name is accepted

**In simple words:** A product can be saved with no name. In the list it appears as a picture and price with a blank title.

**Cause:** [inventory_app/views.py:21](inventory_project/inventory_app/views.py#L21). An empty string `""` is not `NULL`, so the database accepts it, and there is no form validation to catch it.

**Test (fails):** `ProductCreateValidationTest.test_empty_name_is_rejected`: `1 != 0` (saved)

---

### Bug 15: Editing a product with a missing field crashes the server

**In simple words:** If an edit request leaves out a field (for example, only the name is sent), the site crashes instead of keeping the old value or showing an error.

**Cause:** [inventory_app/views.py:45-48](inventory_project/inventory_app/views.py#L45-L48). Each missing field is set to `None`, then `product.save()` on line 53 fails.
Error: `IntegrityError: NOT NULL constraint failed: inventory_app_product.price`

**Test (fails):** `ProductUpdateValidationTest.test_update_with_missing_fields_does_not_crash`: `500`

---

### Bug 16: "Back to Home" link leads to a 404 page

**In simple words:** The "Back to Home" button on the email page goes to the site's front page (`/`), but there is no front page. The user gets "Page not found".

**Cause:** [inventory_app/templates/email_sent.html:97](inventory_project/inventory_app/templates/email_sent.html#L97) links to `href="/"`. Neither [inventory_project/urls.py](inventory_project/inventory_project/urls.py) nor [inventory_app/urls.py](inventory_project/inventory_app/urls.py) defines a URL for `/`. The product list lives at `/products/`.

**Test (fails):** `SendTestEmailTest.test_home_link_on_email_page_works`: `404`

---

## Not confirmed

None. Every suspected bug in sections A and B was reproduced by a failing test.

---

## Checked: works correctly

These were suspected weak spots. The tests show they work as they should, and all of these tests pass.

| What was checked | Result | Test |
|---|---|---|
| **CSRF protection.** A forged form from another website cannot create or delete products. | Works. Requests without a CSRF token are rejected with `403`. `CsrfViewMiddleware` is on ([settings.py:47](inventory_project/inventory_project/settings.py#L47)) and every form has `{% csrf_token %}`. | `CsrfProtectionTest` (2 tests) |
| **Delete by GET.** Just opening the delete link (e.g. from an image tag or a crawler) must not delete. | Works. GET only shows the confirmation page; deleting needs a POST ([views.py:64](inventory_project/inventory_app/views.py#L64)). | `DeleteByGetTest.test_get_on_delete_url_does_not_delete` |
| **HTML/JavaScript in product names (XSS).** | Works. Django escapes the name: `<script>` is shown as text and not run. | `HtmlEscapingTest.test_product_name_is_escaped_on_list_page` |
| **Misspelled duplicate folder `tamplates/`.** | Not used. All templates are loaded from `templates/`. The `tamplates/` folder is leftover clutter that could confuse developers, but it does not affect the app. | `TemplateFolderTest.test_templates_come_from_templates_folder_not_tamplates` |
| **Email sender address.** The view sends from `boyroyal4853@gmail.com` ([views.py:72](inventory_project/inventory_app/views.py#L72)) while logging in as `chaudhary639@gmail.com` ([settings.py:129](inventory_project/inventory_project/settings.py#L129)). | Django builds the email correctly with these addresses. Whether Gmail accepts or rewrites a sender that differs from the logged-in account **can only be checked against real Gmail**, which these tests do not do. | `EmailSenderTest.test_email_is_built_with_from_and_to_addresses` |

---

## Files added or changed

- `inventory_project/inventory_app/tests.py`: unit tests (was an empty stub)
- `inventory_project/functional_tests/__init__.py`, `inventory_project/functional_tests/tests.py`: Playwright browser tests (`StaticLiveServerTestCase`, sync API, `DJANGO_ALLOW_ASYNC_UNSAFE=true`)
- `bug_report.md`: this report

Uploaded test images go to a temporary folder that is deleted after the tests. Emails use Django's in-memory backend, so no real email is sent during the tests.
