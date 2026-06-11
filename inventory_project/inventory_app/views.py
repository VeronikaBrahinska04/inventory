from django.shortcuts import render, redirect, get_object_or_404
from django.core.mail import send_mail
from .models import Product


# Product List
def product_list(request):
    products = Product.objects.all()
    return render(request, 'product_list.html', {'products': products})


# Product Detail
def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    return render(request, 'product_detail.html', {'product': product})


# Create Product
def product_create(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        price = request.POST.get('price')
        image = request.FILES.get('image')
        description = request.POST.get('description')
        quantity = request.POST.get('quantity')

        Product.objects.create(
            name=name,
            price=price,
            image=image,
            description=description,
            quantity=quantity
        )

        return redirect('product_list')

    return render(request, 'product_create.html')


# Update Product
def product_update(request, pk):
    product = get_object_or_404(Product, pk=pk)

    if request.method == 'POST':
        product.name = request.POST.get('name')
        product.price = request.POST.get('price')
        product.description = request.POST.get('description')
        product.quantity = request.POST.get('quantity')

        if request.FILES.get('image'):
            product.image = request.FILES.get('image')

        product.save()

        return redirect('product_list')

    return render(request, 'product_update.html', {'product': product})


# Delete Product
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)

    if request.method == 'POST':
        product.delete()
        return redirect('product_list')

    return render(request, 'product_delete.html', {'product': product})
def send_test_email(request):
    subject = 'Test Email'
    message = 'This is a test email sent from Django.'
    from_email = 'boyroyal4853@gmail.com'
    recipient_list = ['geuvizegebre-9696@yopmail.com']  # Replace with actual recipient email

    try:
        send_mail(subject, message, from_email, recipient_list)
        return render(request, 'Email_Seent.html', {'message': 'Test email sent successfully!'})
    except Exception as e:
        return render(request, 'Email_Seent.html', {'message': f'Error sending email: {str(e)}'})
